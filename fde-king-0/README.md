# FDE King 0

## 1. Methodology and research questions

- **RQ1 component cost:** 500 encryptions and decryptions of a 4096-byte sector, instrumenting seed, mask and data work separately from throughput.
- **RQ2 throughput/latency:** 512- and 4096-byte sectors, 10 trials of 1 MiB each after warm-up; report medians and interquartile ranges. A 64 MiB RAM image is allocated; the report preset uses its first 1 MiB. No disk I/O is timed.
- **RQ3 mask choice:** 10 batches of 100,000 independent or feedback calls, each mapping 48 bytes to 16 bytes. Standalone CBC-MAC evaluates all three stages; sector timings include valid prefix reuse and batching.
- **RQ4 direct reads/parallel recovery:** 200 reads at each of six block positions; 3 trials with every thread count from 1 to 9, over 256 KiB. Also split a sector among threads and trace recovery after a ciphertext-bit error.
- **Optimization check:** interleaved reference/optimized runs, five trials of 50 sectors per direction in the report preset; both must produce identical bytes. Speedup = reference time / optimized time. Reference code is the literal block loop, with CBC sector-seed reuse; both paths share the same mask adapters, so these speedups isolate scheduling changes.
- `MiB/s = bytes × 10⁹ / (2²⁰ × elapsed_ns)`; `ns/byte = elapsed_ns / bytes`; `ns/sector = elapsed_ns / sectors`. Thread speedup = throughput(t) / throughput(1); efficiency = speedup / t. CPU cycles are not estimated.

## 2. Environment and assumptions

| Variable | This measured run |
| --- | --- |
| OS | Linux-6.18.57-x86_64-with-glibc2.41 |
| CPU | INTEL(R) XEON(R) PLATINUM 8573C |
| Available logical CPUs / affinity | 9 / 9 |
| Execution | CPU only; no GPU, CUDA or GPU libraries |
| Python | CPython 3.12.14; GIL enabled: True |
| Threads | RQ1–3: one calling thread; RQ4: 1–9 worker threads |
| Acceleration | AES-NI available: True; CLMUL (field multiplication) available: True |
| Backend | OpenSSL 4.0.1 9 Jun 2026 |
| Timer | perf_counter_ns; nominal resolution 1 ns, not a latency guarantee |
| Host controls | CPU quota: not exposed; turbo, frequency, power mode and background load are not controlled |

- CPU model, OS, Python/backend versions, hardware acceleration, available CPUs, working-set size and power/load conditions can change results. Changing terminals alone should not change the algorithm, but may select a different Python environment. Windows/macOS instructions and CI are supplied; only Linux was executed here.
- The program prints these runtime conditions immediately, then prints the selected batch sizes and worker counts. Full details are saved in `results/environment.json` and the supplied run in `benchmark.log`.
- **Implementation choices:** AES-256 data keys; AES-256 mask/tweak keys for CBC-MAC/XTS. AES-NI is requested for AES operations except the explicit XTS AES-NI-off control; libraries select their native CPU paths. All profiles take a 64-byte key container `K1 || K2`; LRW and SipHash use the first 16 bytes of K1, leaving its other 16 unused. LRW requires that field key to be nonzero. Public deterministic keys are benchmark fixtures; `example.py` uses a random key.
- Sectors and block indices are zero-extended to 16-byte big-endian fields; code indices start at zero. Feedback starts at 16 zero bytes. Complete AES blocks only, without padding/stealing or authentication tags.
- For every feedback construction, `C_j = AES_K2(P_j XOR delta_j) XOR delta_j`. Hash-based **XEX** uses only KMAC128, keyed BLAKE2s/BLAKE2b/BLAKE3 and SipHash-2-4-128. **AES-MAC-CBC** and **LRW-Polynomial** are separate construction names, sharing this outer data transformation.
- CBC-MAC uses the document's three AES stages. LRW uses exactly `((S·a XOR I_j)·a XOR C_prev)·a`, modulo x¹²⁸+x⁷+x²+x+1. A tested bit-order conversion allows native GHASH multiplication with an expanded key reused per worker; the pinned private interface is isolated in `masks.py`. This is the feedback LRW-polynomial proposal, not a claim that it is standardized LRW or proven secure.

## 3. Run in a terminal

1. Extract the ZIP and open `fde-king-0` in VS Code. Install Python 3.12.
2. Create a virtual environment: `python -m venv .venv` (Windows: `py -3.12 -m venv .venv`).
3. Activate: Linux/macOS `source .venv/bin/activate`; Windows PowerShell `.venv\Scripts\Activate.ps1`. Alternatively call that environment's Python directly.
4. Install: `python -m pip install -r requirements.txt`.
5. Run: `python run.py --preset report`. Outputs: raw/summary CSVs in `results/`, six PNGs in `figures/`, and regenerated README tables. `--workers N` changes the maximum thread count.
6. Quick check: `python run.py --preset smoke --out smoke_results`. Full 64 MiB passes: `python run.py --preset full --out full_results`, substantially slower. Full preset was not run for the supplied report.
7. Select a hash by changing one line, `DEFAULT_MASK = 'blake3'`, in `fdebench/engine.py`, or call `Engine('xex', 'blake2s', key=your_64_byte_key)`. Separate constructions use `Engine('cbc_mac', key=...)` and `Engine('lrw_poly', key=...)`. Benchmarks always run every registered profile. Tests: `python -m unittest discover -s tests -v`.

## 4. Results and interpretation

### RQ1 Component cost and optimization

| Construction | Seed | Mask/tweak | Data path | Other |
| --- | --- | --- | --- | --- |
| XTS manual, AES-NI enabled | 2.6% | 86.0% | 10.9% | 0.5% |
| keyed BLAKE2s | 0.1% | 14.5% | 78.5% | 6.9% |
| AES-MAC-CBC | 0.2% | 48.8% | 47.0% | 4.0% |
| LRW-Polynomial | 0.0% | 42.8% | 52.3% | 4.8% |

Shares include Python/native wrapper work and instrumentation, not isolated CPU-instruction costs. Opaque whole-sector library stages are not subdivided. Internal clocks alter execution cost; throughput uses uninstrumented runs.

| Construction | Encryption speedup | Decryption speedup |
| --- | --- | --- |
| XTS manual, AES-NI enabled | 7.60× | 6.51× |
| keyed BLAKE2s | 0.90× | 5.82× |
| AES-MAC-CBC | 1.36× | 23.21× |
| LRW-Polynomial | 1.07× | 2.78× |

- XTS generates its tweaks explicitly, then batches data AES and XORs. AES-NI-off/on controls use the same scheduling; OpenSSL whole-sector XTS remains a separate control.
- AES-MAC-CBC prepares `E(S)` and all `E(I_j XOR E(S))` before the feedback loop. Encryption still needs one mask AES call and one data AES call per block, plus setup batches. Decryption needs only **four native AES calls per sector**: seed, batched middle stage, batched final stage, and batched data decryption. The mathematical AES work remains **3n+1 block evaluations**.
- The fastest hash profile has **0.90×** encryption speedup in the paired check; values below one mean a slowdown, so these changes do not improve every path. Hash-based XEX and LRW batch data AES during decryption. LRW also reuses its expanded multiplication key. No previous sector's plaintext, ciphertext or mask results are cached to improve timings.

![Component cost](figures/rq1_components.png)

### RQ2 Raw throughput and latency

4096-byte sectors, descending encryption throughput.

| Construction | Enc MiB/s | Dec MiB/s | Enc ns/sector | Enc ns/byte |
| --- | --- | --- | --- | --- |
| AES-ECB · bulk | 795.58 | 859.31 | 4,924 | 1.20 |
| AES-XTS · OpenSSL, full sector | 507.50 | 430.43 | 7,701 | 1.88 |
| AES-XTS · manual, AES-NI enabled | 27.24 | 27.09 | 143,387 | 35.01 |
| AES-XTS · manual, AES-NI off | 23.88 | 24.37 | 163,585 | 39.94 |
| XEX · keyed BLAKE2s | 3.33 | 20.02 | 1,174,058 | 286.64 |
| XEX · keyed BLAKE3 | 2.91 | 15.52 | 1,344,531 | 328.25 |
| XEX · keyed BLAKE2b | 2.64 | 15.90 | 1,482,823 | 362.02 |
| LRW-Polynomial | 2.14 | 4.59 | 1,829,992 | 446.78 |
| AES-MAC-CBC | 2.06 | 31.10 | 1,893,374 | 462.25 |
| XEX · SipHash-2-4-128 | 1.98 | 7.99 | 1,971,416 | 481.30 |
| XEX · KMAC128 | 0.58 | 0.85 | 6,792,787 | 1658.40 |

The fastest hash-based XEX profile is **keyed BLAKE2s at 3.33 MiB/s**. AES-MAC-CBC reaches **2.06 MiB/s encryption and 31.10 MiB/s decryption**. Compared with keyed BLAKE2s, its encryption throughput is 0.62× and its decryption throughput is 1.55×. Encryption remains sequential, while decryption benefits from batching. Native AES throughput cannot be inferred from individual Python call timings. Compare optimization speedups within this run; the previous archive ran on a different host.

![Throughput](figures/rq2_throughput.png)

### RQ3 Hash and mask choice

Fastest standalone feedback call first. These calls include input assembly and wrappers; independent versus feedback loops do not isolate a dependency penalty.

| Mask | Dependent ns/call | Enc MiB/s | Dec MiB/s |
| --- | --- | --- | --- |
| keyed BLAKE2s | 629 | 3.33 | 20.02 |
| keyed BLAKE2b | 695 | 2.64 | 15.90 |
| keyed BLAKE3 | 1,212 | 2.91 | 15.52 |
| SipHash-2-4-128 | 1,759 | 1.98 | 7.99 |
| LRW-Polynomial | 4,231 | 2.14 | 4.59 |
| AES-MAC-CBC | 10,733 | 2.06 | 31.10 |
| KMAC128 | 20,938 | 0.58 | 0.85 |

A standalone mask-call ranking does not determine complete-sector decryption speed: CBC-MAC's independent stages can be batched, whereas the current hash adapters still make one Python/native hash call per block. The table therefore reports both mask cost and complete encryption/decryption. Performance is not a security ranking; polynomial hashing is not a general cryptographic hash/PRF.

![Mask cost](figures/rq3_hash_cost.png)

### RQ4 Random access and parallel recovery

| Construction | Read µs | Best threads / speedup | 9 threads: speedup / efficiency |
| --- | --- | --- | --- |
| keyed BLAKE2s | 4.02 | 2 / 1.11× | 0.86× / 9.5% |
| LRW-Polynomial | 6.27 | 1 / 1.00× | 0.08× / 0.9% |
| AES-MAC-CBC | 11.18 | 1 / 1.00× | 0.45× / 5.0% |
| XTS manual, AES-NI enabled | 27.44 | 1 / 1.00× | 0.39× / 4.4% |

Read latency is the median of six position-specific medians, with ciphertext already in RAM. Hash-XEX, AES-MAC-CBC and LRW need only C_j and its preceding ciphertext block, or C_j alone at the first position. Manual XTS derives a requested tweak directly; its Python field multiplication has overhead. The OpenSSL control decrypts the whole sector because this public API has no offset-block interface.

For **keyed BLAKE2s**, best inter-sector decryption speedup is **1.11× at 2 worker(s)**. This measures CPython threads and native-call scheduling, not an algorithmic limit. Thread curves show medians and interquartile bands normalized to the one-thread median; with few trials, small gains and irregular spikes should be rerun before treating them as stable scaling. Encryption is sequential within each feedback sector; decryption ranges are independent.

Changing one bit in ciphertext block 32 damaged plaintext blocks 32–33 in the tested feedback constructions, then recovery occurred at block 34; ECB/XTS damaged only block 32. None authenticates the alteration or prevents whole-sector rollback.

![Direct reads](figures/rq4_random_access.png)
![Thread scaling](figures/rq4_thread_scaling.png)
![Within-sector recovery](figures/rq4_within_sector.png)

## 5. Further considerations

- Repeat on other CPUs/OSs and power modes with the printed conditions, package versions and batch sizes retained. Shared-host noise and different native backends can change close rankings.
- A compiled whole-sector implementation can further reduce per-block dispatch. Compare processes or native multicore execution before concluding that extra cores cannot help.
- Evaluate security separately for the exact feedback constructions; neither an AES-based mask nor fast polynomial multiplication alone establishes a security proof.

Implementation reference: [PyCryptodome buffer and native cipher APIs](https://www.pycryptodome.org/src/cipher/cipher). Construction formulas follow the supplied 18 November document.
