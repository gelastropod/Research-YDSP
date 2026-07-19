# Ciphertext-Ratcheted AES-XTS FDE Prototype

> Can ciphertext-dependent ratcheting improve measurable performance in no-expansion full disk encryption while preserving random access...?

It compares a conventional AES-XTS baseline with sector-scoped and globally scoped ciphertext ratchets.

## Construction

A master secret is expanded with HKDF into three logically independent keys:

- $K_0$ — a 256-bit initial key for AES-128-XTS;
- $K_F$ — a fixed AES-128 key for the tweak update `F`;
- $K_G = K_{G,L} || K_{G,R}$ - two fixed AES-128 keys implementing the 256-bit key update `G`.

For block `i`, the prototype encrypts with real AES-XTS:

$$
C_i = \text{XTS-AES.Enc}(K_i, T_i, P_i)
$$

It then updates the internal state from the ciphertext:

$$
T_{i+1}   = AES(K_F,C_i) \\
K_{i+1,L} = AES(K_{G,L}, K_{i,L} \oplus C_i) \\
K_{i+1,R} = AES(K_{G,R}, K_{i,R} \oplus C_i) \\
K_{i+1}   = K_{i+1,L} || K_{i+1,R}
$$

$K_i$ is input data to $G$, it is never reused as the key of $F$ or $G$. The LBA provides the initial 16-byte XTS tweak. Later ratcheted tweaks are secret internal state rather than public TBC tweaks.

AES-128-XTS requires a 256-bit double-length key, so the report's 128-bit key-update equation is lifted to two independently keyed 128-bit halves. The code uses `cryptography`'s AES-XTS mode rather than a handwritten XEX approximation.

## Compared modes

### Baseline

A whole sector is one conventional XTS data unit under a fixed key and an LBA-derived tweak. It is length-preserving and supports independent sector access.

### Sector ratchet

The state resets at each sector. Tampering can affect later blocks in that sector, while sector-level random access remains available.

### Global ratchet

The final state of one sector seeds the next. Propagation can cross sector boundaries, but direct random access is lost unless the preceding state is supplied.

To preserve the block-level recurrence in the write-up, the ratcheted prototype invokes AES-XTS on one 16-byte block per ratchet step. This is an experimental composition, not conventional IEEE 1619 sector processing.

## Security interpretation

The construction remains no-expansion: plaintext and ciphertext lengths are equal. However, corruption propagation is **not authentication**. Modified ciphertext is not rejected; it decrypts to corrupted bytes. The project should measure speed, throughput, propagation, random-access depth, parallelism, and state-recovery cost separately.

## Files

- `ratchet_fde.py` — AES-XTS baseline and ratcheted construction.
- `test_functionality.py` — assert-based checks with coloured expected/actual output.
- `benchmark.py` — repeated timing, mean/median/stdev, throughput, ratios, and component profiling.
- `requirements.txt` — Python dependency.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt
```

## Run functionality checks

```bash
python test_functionality.py
```

Every check prints its expected and actual result. A failed comparison raises `AssertionError`.

## Run performance analytics

```bash
python benchmark.py
```

Example with more repetitions and CSV output:

```bash
python benchmark.py --repeats 9 --iterations 200 --sectors 32 \
  --blocks-per-sector 32 --csv results.csv
```

## References

- NIST SP 800-38E, *The XTS-AES Mode for Confidentiality on Storage Devices*.