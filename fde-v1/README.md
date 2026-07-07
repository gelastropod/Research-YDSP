# Ratcheted FDE V1 demo

Can ciphertext-dependent ratcheting be added to a full-disk-encryption (FDE)-esque construction, while preserving enough random access to remain usable?

## Construction

For each 128-bit block:

$$C_i = AES_{K_i}(P_i \oplus T_i) \oplus T_i$$
$$T_{i+1} = F_{K_F}(C_i) = AES_{K_F}(C_i)$$
$$K_{i+1} = G_{K_G}(K_i \oplus C_i) = AES_{K_G}(K_i \oplus C_i)$$

Key separation is explicit:

- $K_i$ is the evolving data-encryption key state.
- $K_F$ is the fixed secret key for the tweak-ratchet permutation.
- $K_G$ is the fixed secret key for the key-ratchet permutation.

$K_i$ is **not** reused as the key for `F` or `G`. It is input data to `G`.

## Two scopes

### 1. Sector-scoped ratchet

Each sector starts from a deterministic initial state based on its LBA.

- Preserves sector-level random access
- Tamper propagation stays inside the sector
- More compatible with FDE

### 2. Global ratchet

The final state of sector \(i\) becomes the initial state of sector \(i+1\).

- A change in an early sector affects all later sectors
- Direct random access is lost
- Useful as a negative-control experiment

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
python experiments.py
python asserts.py
```

Expected results:

- Sector-scoped ratcheting decrypts LBA 3 directly
- Global ratcheting fails to decrypt LBA 3 directly unless all previous sectors are processed
- Flipping one ciphertext byte corrupts multiple downstream plaintext blocks

## Research limitations

This code deliberately omits:

- ciphertext stealing
- real disk I/O
- authentication/integrity
