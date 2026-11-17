# Adding a new encryption scheme

This document explains how the scheme machinery in `fde-drive-0` works in
detail — what every helper function does, what the return codes mean — and
walks through adding a new scheme end to end, using a chained XEX
construction as the worked example. All paths are relative to `fde-drive-0/`.

---

## 1. Return-code and error conventions

The whole codebase uses the same conventions:

| Return value | Meaning |
|---|---|
| `0` | Success |
| `-1` | Failure (bad arguments, or an OpenSSL call failed) |
| `NULL` (pointer-returning functions) | Failure — `fde_worker_new` can return NULL |

Details:

- `int` functions return **`0` on success, `-1` on failure**. No errno-style
  codes, no partial failure information. On `-1`, the contents of the output
  buffer are unspecified (the function may have written some blocks before
  failing — callers must not use them).
- `fde_worker_new` returns `NULL` on allocation or cipher-init failure.
  Always check it.
- `fde_scheme_name` never fails — it returns `"unknown"` for out-of-range
  values instead.
- `void` functions (`fde_ratchet_blake3_update`, `fde_xts_mul_alpha`,
  `encode_*`, `xor_block`, `fde_worker_free`) cannot fail.
- Internally, a `-1` almost always means an OpenSSL `EVP_*` call returned
  something other than `1`, or the byte count produced didn't match what was
  expected (see `fixed_block` below).

---

## 2. The OpenSSL EVP mental model

Everything crypto goes through OpenSSL's high-level EVP API. Three calls
matter:

```c
EVP_CIPHER_CTX *EVP_CIPHER_CTX_new(void);        /* allocate a context object */
int EVP_EncryptInit_ex(ctx, cipher, impl, key, iv);
int EVP_EncryptUpdate(ctx, out, &out_len, in, in_len);
int EVP_EncryptFinal_ex(ctx, out, &final_len);
/* same trio with Decrypt* */
```

A `EVP_CIPHER_CTX` is a **configured cipher machine**. Init-time you tell it:

- **cipher** — which algorithm+mode (`EVP_aes_256_ecb()`, `EVP_aes_128_ecb()`,
  `EVP_aes_256_xts()`). Passing `NULL` means "keep whatever cipher was set
  before" — this is the trick `dynamic_block` uses to swap only the key.
- **key** — the raw key bytes (must match the cipher's key size: 16 B for
  AES-128, 32 B for AES-256). Crucially, **the key schedule is expanded at
  Init time** — that's the expensive part of AES setup, so you want to do it
  as rarely as possible.
- **iv** — IV/tweak if the mode needs one; ECB ignores it (`NULL`).

Then `Update` processes data: feed bytes in, get bytes out. With padding
disabled (this code always disables it) and ECB mode, a 16-byte input
produces exactly 16 bytes of output, immediately, every call — ECB is
stateless across calls, so a ctx becomes a pure "block in → block out"
function with the key baked in.

`Final` flushes any buffered padding — with padding disabled and ECB it's a
no-op, and this code only calls it in the whole-sector OpenSSL XTS path, not
in the per-block helpers.

---

## 3. The worker (`struct fde_worker`)

`fde.c:12-28`. A worker bundles everything long-lived:

```c
struct fde_worker {
    fde_keys keys;                       /* copy of the device-wide keys     */
    uint8_t xts_combined_key[64];        /* k1||k2 for OpenSSL XTS           */
    EVP_CIPHER_CTX *ecb_enc, *ecb_dec;   /* AES-256-ECB under ecb_key        */
    EVP_CIPHER_CTX *xts_data_enc, *xts_data_dec, *xts_tweak_enc;
    EVP_CIPHER_CTX *seed_enc;            /* AES-256-ECB under ratchet_k0     */
    EVP_CIPHER_CTX *ratchet_enc;         /* AES-256-ECB under ratchet_kg     */
    EVP_CIPHER_CTX *dynamic128_enc, *dynamic128_dec;  /* AES-128-ECB, rekeyed per call */
    EVP_CIPHER_CTX *dynamic256_enc, *dynamic256_dec;  /* AES-256-ECB, rekeyed per call */
    EVP_CIPHER_CTX *openssl_xts_enc, *openssl_xts_dec;/* full-sector XTS      */
};
```

Two kinds of contexts:

- **Dedicated** — init'd once in `fde_worker_new` with a cipher *and* a real
  key. From then on the key schedule is cached and each block op is just the
  raw AES permutation. Use these when your scheme encrypts under a fixed key.
- **Dynamic** — init'd once with a cipher and a *dummy zero key*. The key is
  replaced on every single call via `dynamic_block`. Use these when the key
  itself changes per block (the ratchet schemes use the evolving state as
  the key). You pay an AES key expansion per block — visible in `data_ns`.

Lifecycle: `fde_worker_new(&keys)` (allocate + init all ctxs, `fde.c:158`) →
use for unlimited encrypt/decrypt calls → `fde_worker_free` (`fde.c:201`).
Workers are **not thread-safe** — `benchmark.c` creates one worker per
thread.

To add a dedicated ctx for a new scheme:

1. `EVP_CIPHER_CTX *xex_enc, *xex_dec;` fields in the struct.
2. In `fde_worker_new`:
   `worker->xex_enc = new_cipher_ctx(EVP_aes_256_ecb(), keys->xex_k2, 1);`
   (last arg: `1` = encrypt direction, `0` = decrypt — ECB needs both because
   the ctx direction is fixed at init).
3. Add both to the big NULL check at `fde.c:188` (any failure frees
   everything and returns NULL).
4. `EVP_CIPHER_CTX_free` both in `fde_worker_free`.

---

## 4. Function reference (src/fde.c)

### Timing

```c
static uint64_t now_ns(void)
```
Returns `CLOCK_MONOTONIC` in nanoseconds; `0` if the clock call fails. Take a
timestamp before a phase and hand it to `profile_add` after.

```c
static void profile_reset(fde_profile *profile)
```
Zeroes `seed_ns`, `data_ns`, `evolution_ns`. Called at the top of
`fde_encrypt`/`fde_decrypt` so each call's counters start fresh. No-op on
NULL.

```c
static void profile_add(uint64_t *field, uint64_t start)
```
`*field += now_ns() - start` — accumulates elapsed time into one counter.
No-op if `field` is NULL. You pass `&profile->data_ns` etc.

**Usage pattern** (repeated dozens of times in the file):

```c
uint64_t start = profile == NULL ? 0 : now_ns();   /* don't call clock if unused */
/* ... do the work ... */
if (profile != NULL) profile_add(&profile->data_ns, start);
```

Callers may pass `profile == NULL` to skip timing entirely; the
`profile == NULL ? 0 : now_ns()` guard avoids even reading the clock then.

**Which counter gets what:**

| Counter | Meaning | Examples |
|---|---|---|
| `seed_ns` | once-per-sector setup | `seed_state`, `xts_seed` calls |
| `data_ns` | per-block data transformation | the AES block call + XORs |
| `evolution_ns` | per-block state/tweak evolution between blocks | ratchet update, `mul_alpha`, tweak derivation |

These three fields become the `seed_ns`, `data_n`, `sevolution_ns`, `io_ns`
columns in the drive-test CSV and the percentage breakdown printed at the end.

### Byte utilities

```c
static void encode_u64_le(uint64_t value, uint8_t out[16])
static void encode_u32_le(uint32_t value, uint8_t out[16])
```
Writes `value` little-endian into a **zero-filled** 16-byte buffer (the
remaining bytes are 0). This is how you turn the sector number `S` or a block
index `I_j` into the fixed 128-bit strings the constructions want — e.g.
`encode_u64_le(sector, s_enc)` produces the 128-bit `S` for your XEX tweak.

```c
static void xor_block(uint8_t out[16], const uint8_t a[16], const uint8_t b[16])
```
`out = a ⊕ b` for 16 bytes. Plain loop, no SIMD.

### OpenSSL wrappers

```c
static EVP_CIPHER_CTX *new_cipher_ctx(const EVP_CIPHER *cipher,
                                      const uint8_t *key, int encrypt)
```
Allocates a ctx and initializes it with `cipher` + `key` + padding disabled.
`encrypt` selects `EVP_EncryptInit_ex` (1) or `EVP_DecryptInit_ex` (0).
Returns the ctx, or `NULL` if allocation or init failed — callers must check.
Used only inside `fde_worker_new`.

```c
static int fixed_block(EVP_CIPHER_CTX *ctx, int encrypt,
                       const uint8_t in[16], uint8_t out[16])
```
**Encrypts or decrypts exactly one 16-byte block through a context whose key
is already set.** Concretely it calls:

```c
encrypt ? EVP_EncryptUpdate(ctx, out, &written, in, 16)
        : EVP_DecryptUpdate(ctx, out, &written, in, 16);
return ok == 1 && written == 16 ? 0 : -1;
```

"Fixed" = the key is fixed (baked into `ctx` at `fde_worker_new` time); the
function touches nothing but the data. So `fixed_block(worker->xex_enc, 1,
masked, out)` means "AES-256-ECB-encrypt `masked` under K2". `written` is the
byte count OpenSSL produced — the check `written == 16` catches any case
where EVP buffered or refused the block (shouldn't happen with ECB+no
padding, but it's the integrity check). Returns `0` success / `-1` failure.

```c
static int dynamic_block(EVP_CIPHER_CTX *ctx, int encrypt,
                         const uint8_t *key, const uint8_t in[16],
                         uint8_t out[16])
```
Same one-block operation, but **re-keys `ctx` first**: it calls
`EVP_*Init_ex(ctx, NULL, NULL, key, NULL)` — `NULL` cipher means "keep the
cipher set at creation" (AES-128-ECB for `dynamic128_*`, AES-256-ECB for
`dynamic256_*`), and only the key pointer is replaced. Then one `Update`.
Returns `0`/`-1` on the same `ok && written == 16` check.

This is how the ratchet schemes encrypt each block under a different key
(the current ratchet `state`). Each call costs an AES key expansion — that's
why it exists as a separate helper rather than being the default.

### Per-sector seed derivation

```c
static int seed_state(fde_worker *worker, uint64_t sector, uint8_t state[16])
```
`state = AES-256-ECB_Enc(ratchet_k0, encode_u64_le(sector))`.
This is the "KDF(master_key, S)" step — a per-sector secret derived from the
sector index. Used to initialize the 16-byte ratchet state (and the first 16
bytes of the 32-byte BLAKE3-ratchet state). Time it under `seed_ns`. Returns
`0`/`-1`.

```c
static int xts_seed(fde_worker *worker, uint64_t sector, uint8_t tweak[16])
```
Identical shape, keyed by `xts_k2` — this is XTS's `T0 = E_K2(sector)`.

### Ratchet evolution (public functions, also used internally)

```c
int fde_ratchet_aes_update(fde_worker *worker, uint8_t state[16],
                           const uint8_t ciphertext[16])
```
`state ← AES-256-ECB_Enc(ratchet_kg, state ⊕ ciphertext)`. Keyed 16-byte
state evolution; NULL args → `-1`, else `0`.

```c
void fde_ratchet_blake3_update(uint8_t state[32], const uint8_t ciphertext[16])
```
`state ← BLAKE3(state ‖ ciphertext)` — unkeyed 32-byte evolution using the
vendored BLAKE3 (`blake3_hasher_init` → `update` → `finalize` with 32-byte
output). Cannot fail. This is also your template for calling BLAKE3 directly.

### Index helpers

```c
static int indices_are_consecutive(const uint32_t *indices, size_t blocks)
```
True if `indices[j] == indices[0] + j` for all j (or `indices == NULL`, or
fewer than 2 blocks). Enables fast sequential paths — e.g. XTS can multiply
the tweak by α once per block instead of recomputing α^I_j from scratch.

```c
static uint32_t index_at(const uint32_t *indices, size_t j)
```
`indices == NULL ? (uint32_t)j : indices[j]`. **Always read `I_j` through
this** so `NULL` (meaning "indices are 0..n-1") works.

### Validation and dispatch

```c
static int validate_arguments(fde_worker *worker, fde_scheme scheme,
                              const uint8_t *input, size_t blocks,
                              uint8_t *output)
```
Returns `0` iff: `worker`, `input`, `output` are non-NULL, `scheme` is within
`[0, FDE_SCHEME_COUNT)`, and `blocks > 0`. Else `-1`. Called at the top of
every public crypt function — a NULL `indices` is legal and is *not* checked
here (helpers handle it).

```c
int fde_encrypt(...) / int fde_decrypt(...)         /* fde.c:470, :497 */
```
Validate → `profile_reset` → `switch (scheme)` → call the matching
`*_crypt` impl with `encrypt = 1/0` → return its `0`/`-1`.

```c
int fde_decrypt_target(worker, scheme, ciphertext, indices, sector,
                       blocks, target, plaintext[16])     /* fde.c:602 */
```
Recovers **one** plaintext block:
- ECB / XTS: compute that block's tweak, decrypt directly — O(1).
- Chained schemes: replay `j = 0..target` carrying state, because block `j`'s
  tweak/key depends on `C_{j-1}` — O(target).
The random-access benchmark (`--rq3`) calls this; a new scheme needs a branch
or random access silently computes garbage — actually it falls into the
trailing BLAKE3 block, so do add an explicit branch.

### Scheme metadata

```c
const char *fde_scheme_name(fde_scheme scheme)      /* fde.c:123 */
```
`names[FDE_SCHEME_COUNT]` indexed by enum — **entries must be in enum
order**. Out-of-range → `"unknown"`.

```c
int fde_scheme_uses_indices(fde_scheme scheme)      /* fde.c:136 */
```
Does the scheme consume the `indices` array (XTS, CTR)? Benchmark code uses
this to decide whether to pass real indices.

```c
int fde_scheme_is_ratchet(fde_scheme scheme)        /* fde.c:141 */
```
Is the scheme state-chained? **Gotcha:** implemented as
`scheme >= FDE_RATCHET_CTR_AES` — it assumes ratchet schemes form a
contiguous suffix of the enum. A new chained scheme must either be inserted
inside that range or the predicate rewritten as a `switch`.

---

## 5. The `*_crypt` contract

Your implementation is a static function matching this shape:

```c
static int my_scheme_crypt(fde_worker *worker, int encrypt,
                           const uint8_t *input, const uint32_t *indices,
                           uint64_t sector, size_t blocks, uint8_t *output,
                           fde_profile *profile);
```

Contract:

- `input`/`output` are `blocks * 16` bytes. `encrypt == 1`: `input` is
  plaintext, write ciphertext to `output`. `encrypt == 0`: reversed.
- `indices` may be NULL → read `I_j` via `index_at`.
- `sector` is the absolute on-device sector index (your `S`).
- `profile` may be NULL → guard all timing.
- Return `0` on full success, `-1` on any failure. Partial writes are OK —
  callers treat `-1` as "output is garbage" and abort.
- You may read the worker's keys/ctxs but must not mutate them (the ctxs are
  shared state — `Update` calls are fine since ECB is stateless, but don't
  re-init a dedicated ctx).

---

## 6. Worked example: chained XEX

Construction (block = 16 B, sector = `n` blocks):

```
C_0 = 0^128
Δ_j = KH(K1, S ‖ I_j ‖ C_{j-1})                    /* 48-byte input, 16-byte output */
C_j = AES-256_Enc(K2, P_j ⊕ Δ_j) ⊕ Δ_j
```

KH = BLAKE3 keyed mode (32-byte K1, 16-byte output); the unkeyed variant UH
is plain `blake3_hasher_init`. Sector is encoded with `encode_u64_le`, block
index with `encode_u32_le` — giving the 48-byte `S‖I_j‖C_{j-1}` input.

```c
static int xex_ratchet_crypt(fde_worker *worker, int encrypt,
                             const uint8_t *input, const uint32_t *indices,
                             uint64_t sector, size_t blocks, uint8_t *output,
                             fde_profile *profile) {
    uint8_t s_enc[16];
    uint8_t c_prev[16] = {0};               /* C_0 = 0^128 */
    encode_u64_le(sector, s_enc);

    for (size_t j = 0; j < blocks; ++j) {
        const uint8_t *src = input + 16 * j;
        uint8_t *dst = output + 16 * j;
        uint8_t delta[16], masked[16], inner[16], kh_in[48];

        /* Δ_j = KH(K1, S‖I_j‖C_{j-1}) — charged to evolution_ns */
        uint64_t start = profile == NULL ? 0 : now_ns();
        memcpy(kh_in, s_enc, 16);
        encode_u32_le(index_at(indices, j), kh_in + 16);
        memcpy(kh_in + 32, c_prev, 16);
        blake3_hasher h;
        blake3_hasher_init_keyed(&h, worker->keys.xex_k1);
        blake3_hasher_update(&h, kh_in, sizeof(kh_in));
        blake3_hasher_finalize(&h, delta, 16);   /* BLAKE3 is an XOF: 16 B out */
        if (profile != NULL) profile_add(&profile->evolution_ns, start);

        /* block transform — charged to data_ns */
        start = profile == NULL ? 0 : now_ns();
        xor_block(masked, src, delta);
        if (fixed_block(encrypt ? worker->xex_enc : worker->xex_dec,
                        encrypt, masked, inner) != 0) {
            return -1;
        }
        xor_block(dst, inner, delta);
        if (profile != NULL) profile_add(&profile->data_ns, start);

        /* chain on C_j: encrypt produced it in dst, decrypt read it in src */
        memcpy(c_prev, encrypt ? dst : src, 16);
    }
    return 0;
}
```

`fde_decrypt_target` branch — replay the chain since Δ_j needs `C_{j-1}`:

```c
if (scheme == FDE_XEX_RATCHET) {
    uint8_t s_enc[16], c_prev[16] = {0};
    encode_u64_le(sector, s_enc);
    for (size_t j = 0; j <= target; ++j) {
        uint8_t delta[16], masked[16], inner[16], kh_in[48];
        memcpy(kh_in, s_enc, 16);
        encode_u32_le(index_at(indices, j), kh_in + 16);
        memcpy(kh_in + 32, c_prev, 16);
        blake3_hasher h;
        blake3_hasher_init_keyed(&h, worker->keys.xex_k1);
        blake3_hasher_update(&h, kh_in, sizeof(kh_in));
        blake3_hasher_finalize(&h, delta, 16);
        memcpy(c_prev, ciphertext + 16 * j, 16);     /* C_j for next iter */
        if (j == target) {
            xor_block(masked, ciphertext + 16 * j, delta);
            if (fixed_block(worker->xex_dec, 0, masked, inner) != 0)
                return -1;
            xor_block(plaintext, inner, delta);
        }
    }
    return 0;
}
```

(Place this before the final catch-all `{ ... }` block at `fde.c:659`,
otherwise your scheme falls through to the BLAKE3-ratchet logic and decrypts
garbage.)

---

## 7. Registration checklist

| # | File / location | Change |
|---|---|---|
| 1 | `include/fde.h:15` | `FDE_XEX_RATCHET = 6` in enum; `FDE_SCHEME_COUNT = 7`. If new key material: `xex_k1[32], xex_k2[32]` in `fde_keys` |
| 2 | `src/fde.c:145` | init the new keys in `fde_default_keys` |
| 3 | `src/fde.c` worker | `xex_enc`/`xex_dec` fields; create under `xex_k2` in `fde_worker_new`; NULL-check (`:188`); free (`:201`) |
| 4 | `src/fde.c` | `xex_ratchet_crypt` (worked example above) |
| 5 | `src/fde.c:478,505` | `case FDE_XEX_RATCHET:` in `fde_encrypt` and `fde_decrypt` |
| 6 | `src/fde.c:123,136,141` | name in `names[]` (**enum order**); `uses_indices` → true; `is_ratchet` → true (see gotcha, §4) |
| 7 | `src/fde.c:602` | `fde_decrypt_target` branch |
| 8 | `tests/test_drive.c:56` | `{"xex", FDE_XEX_RATCHET}` in `scheme_aliases` |
| 9 | `scripts/run_drive_schemes.sh:26` | add `xex` to `ALL_SCHEMES` |
| 10 | `src/benchmark.c` (optional) | `BENCH_XEX` enumerator (`:32`), `bench_name` entry (`:104`), `implementation_scheme` case (`:119`) |

No makefile changes — `fde.c` is already in `LIB_SRCS`. `fde-c-3` holds an
identical copy of `fde.h`/`fde.c`; mirror edits there for parity.

---

## 8. Verification checklist

- `make test` — `tests/test_fde.c` iterates all schemes; it encrypts then
  decrypts and compares, so a non-inverting scheme fails immediately.
- `make sanitize` — ASan/UBSan catch ctx leaks and buffer errors.
- `make test-drive DRIVE_DEVICE=/dev/sdX DRIVE_SCHEME=xex DRIVE_OFFSET=…
  DRIVE_COUNT=…` on a scratch region.
- Determinism check: same plaintext + sector + indices → same ciphertext.
  Different `sector` → different ciphertext (S enters the tweak).
- Expected timing profile for this design: `data_ns` ≈ AES cost,
  `evolution_ns` ≈ KH cost, `seed_ns` ≈ 0 (no per-sector seed — S is just
  encoded inline). If you add per-sector `K_S = KH(K1, S)`, that cost belongs
  in `seed_ns`.
