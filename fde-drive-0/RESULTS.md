# XEX mask-candidate measurements

Measurements to be filled in after benchmarking on the reference machine
(AMD Ryzen 7 8845HS, OpenSSL 3.0.13, repository build flags). Numbers from
other machines are not comparable.

## Notes

- **Shared K2.** For benchmarking, all XEX schemes encrypt data with
  AES-256 under `keys->xts_k1` (the `xts_data_enc`/`xts_data_dec`
  contexts) — the same key the XTS baseline uses. A deployment must give
  XEX its own AES data key, independent of the mask key K1.
- **K1 (mask key).** `keys->hash_key`, 32 bytes, for every keyed
  candidate. GHASH and SipHash use only the first 16 bytes.
- **BLAKE2b change.** `kh_blake2b` now requests a native 16-byte digest
  (`OSSL_MAC_PARAM_SIZE = 16`, nn = 16 in the parameter block). This is a
  different function from the previous truncate-64-to-16 version, so
  XEX-BLAKE2B ciphertexts changed and its timing was re-measured.
- **GHASH key independence.** H is the first 16 bytes of `hash_key`. It
  is deliberately *not* `AES_K2(0^128)` as in GCM — the security argument
  needs H independent of the AES key. GHASH is a bitwise reference
  implementation (SP 800-38D §6.3 Algorithm 1).
- **Negative control.** Ratchet-XEX-SHA3 is the unkeyed `UH` variant; it
  serves as the negative-control baseline, not a keyed candidate.

## Pending tables

- ns per mask update (component-breakdown method)
- 1 GiB drive throughput in MB/s per scheme
- parallel-scaling rows
