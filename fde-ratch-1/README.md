# FDE Ratchet Benchmark V1.1
> 3rd September 2026 (post-Task 9)

This repository implements and measures the four Task 9 construction families: 
1. Unratcheted AES-ECB,
2. Unratcheted AES-XTS (current standard),
3. Ratcheted AES-CTR, and
4. Ratcheted AES-CBC.

The ratchets are tested with AES and four 256-bit hash-state choices, <b>strictly in C environments</b>

## 1. Research Questions and Methodology

### RQ1: Where does encryption and decryption time go?

- For each construction, what percentage of instrumented time is spent on sector seeding, the AES data path, and XTS tweak evolution or ratchet-state evolution?
- The benchmark encrypts and decrypts one 4096-byte sector for 500 iterations per scheme.
- The percentages use the sum of the three internally timed components. An outer wall-clock time is also exported to reveal instrumentation overhead.

### RQ2: How do throughput and latency scale?

- How do throughput and per-sector latency change with construction, sector size, and total in-memory volume?
- Sector sizes are 512 and 4096 bytes. Volumes are 1 MiB and 32 MiB. Each combination is run for five trials for encryption and decryption.
- The exported measures are mean and median MiB/s, mean ns/sector, mean and median ns/byte, and mean cycles/byte where the processor exposes a timestamp counter.
- `ns/byte` is a derived average, `elapsed nanoseconds / total processed bytes`; no attempt is made to time individual bytes.
- The asymptotic question is evaluated against `n`, the number of 16-byte intra-sector blocks.

### RQ3: Which ratchet primitive is fastest?

- Which secure state-update function has the lowest update cost and the highest end-to-end throughput?
- One million dependent updates are timed for AES-256, BLAKE3, BLAKE2s-256, SHA3-256, and SHA-256.
- The same hash choices are then measured inside both CTR-ratcheting and CBC-ratcheting by the RQ2 end-to-end benchmark.
- BLAKE2s-256 was selected instead of BLAKE2b because OpenSSL 3 exposes an exact 32-byte BLAKE2s result, whereas its standard BLAKE2b EVP interface returns 64 bytes. SHA-256 is included as a secure performance control, but its length-extension property makes it less attractive for this unkeyed concatenation design than BLAKE3, BLAKE2s, or SHA3.

### RQ4: What do random access and parallelism cost?

- Random access recovers blocks 1, 32, 64, 128, 192, and 256 from a 4096-byte sector. Each point uses 1000 warm-cache samples and 80 cache-thrashed samples and reports mean, median, and standard deviation.
- Parallel scaling encrypts a 64 MiB in-memory volume of independent 4096-byte sectors for five trials at every integer thread count from 1 through the detected logical CPU count, capped at 16 by default.
- Set `FDE_MAX_THREADS=N` to choose another upper limit. The included run detected 9 logical CPUs and measured all thread counts from 1 through 9.
- Thread speedup and efficiency are

  \[
  S(t)=\frac{T_t}{T_1}, \qquad E(t)=\frac{S(t)}{t},
  \]

  where `T_t` is throughput with `t` threads. Efficiency is reported as a fraction in the CSV and as a percentage in this document.

## 2. How to run in a VS Code terminal

### Linux

1. Install a C compiler, Make, OpenSSL development headers, Python 3, and `venv`. For Ubuntu or Debian:

   ```sh
   sudo apt update
   sudo apt install build-essential pkg-config libssl-dev python3 python3-venv
   ```

2. Open the extracted `fde-ratchet-bench` folder in VS Code and open **Terminal > New Terminal**.

3. Create the plotting environment and install Matplotlib:

   ```sh
   python3 -m venv .venv
   . .venv/bin/activate
   python3 -m pip install -r requirements.txt
   ```

4. Run the complete reproducible workflow:

   ```sh
   ./scripts/run_all.sh
   ```

### macOS

1. Install the command-line tools and dependencies:

   ```sh
   xcode-select --install
   brew install openssl@3 pkg-config python
   ```

2. Open the project folder and a VS Code terminal, then run:

   ```sh
   python3 -m venv .venv
   . .venv/bin/activate
   python3 -m pip install -r requirements.txt
   make CPPFLAGS="$(pkg-config --cflags openssl)" LDLIBS="$(pkg-config --libs openssl) -lm -pthread" test
   ./scripts/run_all.sh
   ```

### Windows

1. Install WSL2 with Ubuntu, then open the project through the VS Code **WSL** extension. The program uses POSIX threads and is supported on Windows through WSL2, not as a native MSVC build.

2. In the WSL terminal, follow the Linux commands above.

### Useful individual commands

1. Build and run correctness tests:

   ```sh
   make test
   ```

2. Run AddressSanitizer and UndefinedBehaviorSanitizer checks:

   ```sh
   make sanitize
   ```

3. Run the shorter development benchmark:

   ```sh
   ./build/fde_bench --quick results_quick
   ```

4. Run one research question only:

   ```sh
   ./build/fde_bench --rq1 results
   ./build/fde_bench --rq2 results
   ./build/fde_bench --rq3 results
   ./build/fde_bench --rq4 results
   ```

5. Regenerate graphs from existing CSVs:

   ```sh
   python3 scripts/plot_results.py results figures
   ```

- Expect one CSV per measurement family in `results/`: `component_breakdown.csv`, `throughput.csv`, `ratchet_primitives.csv`, `random_access.csv`, and `parallel_scaling.csv`.
- Expect seven PNG graphs in `figures/`, including throughput, ns/byte, ratchet cost, random-access latency, and per-scheme thread speedup and efficiency.
- `results/environment.txt` records the compiler, OpenSSL, operating system, CPU, and relevant instruction flags for the local run.

## 3. Assumptions and Modifications to Pseudocode

- The sector and volume buffers are allocated with `malloc`; the program simulates contiguous in-memory sectors and performs no disk reads or writes. Each benchmark allocates plaintext, ciphertext, output, and block-index arrays at the size needed for that experiment and frees them afterward.
- Each AES block is 16 bytes. Only sector sizes divisible by 16 are benchmarked, so ciphertext stealing and padding are outside this experiment.
- Sector identifiers are encoded as one 128-bit little-endian block. Intra-sector indices are zero-based in C. The Task 9 position `I[j]` is represented by `indices[j]`, with sequential sectors using `0,1,...,n-1`.
- The normal XTS throughput path computes `T0 = AES-128(K2,S)` once and advances the tweak once per block with `MUL_ALPHA`. This is algebraically identical to recomputing `T0 * alpha^I[j]` for sequential indices, but avoids the literal nested loop. A separate `AES-XTS-literal-indexed` RQ1 row validates and exposes the cost of the literal pseudocode. Random target recovery follows the indexed semantics and advances from `T0` to the requested position.
- `AES-XTS-OpenSSL-full-sector` is an explicit optimized-library control. It submits a complete sector to OpenSSL and is not treated as equivalent to a per-block API timing. The manual XTS implementation is the fair block-by-block comparison.
- AES ratchets follow the Task 9 state widths: `K = AES-256(K0,S)` produces a 16-byte state; the data operation uses that state as an AES-128 key; and evolution uses `AES-256(KG,K xor C[j])`.
- Hash ratchets need a 32-byte state. Rather than zero-padding the 16-byte result of one AES call, the 32-byte `K0` is split into `K0L || K0R`, and the seed is expanded as
   $$
   K_{S,0}={AES_{128}}(K_{0L},S)\;||\;{AES_{128}}(K_{0R},S).
   $$

   Every data block therefore uses AES-256 from the start. Evolution is `K = H(K || C[j])`, where `K` is 32 bytes, `C[j]` is 16 bytes, and `H` returns 32 bytes.
- BLAKE3 uses its supplied portable C implementation. BLAKE2s-256, SHA3-256, SHA-256, and AES use OpenSSL EVP contexts. Persistent contexts are reset for each transition so allocation is not included in every update.
- The included correctness run passed the BLAKE3 official empty-input vector, independent OpenSSL hash-transition references, the two-AES-call seed expansion check, round trips for every scheme at 512 and 4096 bytes, manual XTS comparison against both literal XTS and OpenSSL XTS, index semantics, target recovery, AddressSanitizer, and UndefinedBehaviorSanitizer.
- ALL RESULTS ARE RUN ON Linux 6.18 x86-64 with GCC 13.3.0, OpenSSL 3.0.13, and an AMD EPYC 9V74 allocation exposing 9 logical CPUs. The CPU advertised AES-NI, and OpenSSL can dispatch AES EVP operations to <b>hardware acceleration</b>.

## 4. Research-question answers

### RQ1 answer: component cost

| Construction | Evolution, encrypt | Evolution, decrypt | Data path, encrypt | Seed, encrypt |
|---|---:|---:|---:|---:|
| AES-XTS manual | 44.03% | 42.78% | 55.73% | 0.24% |
| CTR ratchet, AES | 29.32% | 28.65% | 70.58% | 0.11% |
| CTR ratchet, BLAKE3 | 51.53% | 51.11% | 48.39% | 0.08% |
| CBC ratchet, AES | 23.87% | 21.92% | 76.02% | 0.11% |
| CBC ratchet, BLAKE3 | 53.01% | 51.36% | 46.91% | 0.08% |

- Sector seeding is negligible at no more than 0.25% of instrumented time.
- AES evolution is substantially cheaper: about 24% to 29% of ratcheted encryption time, against about 52% to 53% for BLAKE3. Decryption shows the same ordering.
- The manual XTS `MUL_ALPHA` evolution is cheap in absolute terms but takes about 43% to 44% of finely instrumented time because the AES data calls are hardware accelerated.
- The literal indexed XTS row spends 92.85% on repeated tweak evolution. It is a pseudocode-cost observation, not the sequential XTS performance baseline.
- ECB, sequential XTS, and every ratchet perform `O(n)` work for `n` intra-sector blocks. Literal recomputation of every sequential `alpha^I[j]` is `O(n^2)` when `I[j]=j`, which is why the recurrence is used for throughput.

### RQ2 answer: throughput, latency, and ns/byte

Representative encryption results for 4096-byte sectors over 32 MiB are:

| Construction | MiB/s | ns/sector | ns/byte | cycles/byte |
|---|---:|---:|---:|---:|
| AES-ECB | 954.85 | 4,091 | 1.00 | 2.59 |
| AES-XTS manual, block path | 351.98 | 11,098 | 2.71 | 7.03 |
| OpenSSL XTS, full sector control | 3,226.59 | 1,211 | 0.30 | 0.77 |
| CTR ratchet, AES | 117.16 | 33,340 | 8.14 | 21.13 |
| CBC ratchet, AES | 120.34 | 32,461 | 7.93 | 20.57 |
| CTR ratchet, BLAKE3 | 64.45 | 60,605 | 14.80 | 38.41 |
| CBC ratchet, BLAKE3 | 63.10 | 61,907 | 15.11 | 39.24 |
| CTR ratchet, SHA-256 | 38.54 | 101,353 | 24.74 | 64.24 |
| CBC ratchet, SHA-256 | 37.19 | 105,040 | 25.64 | 66.58 |
| CTR ratchet, BLAKE2s-256 | 28.99 | 134,727 | 32.89 | 85.39 |
| CBC ratchet, BLAKE2s-256 | 28.16 | 138,728 | 33.87 | 87.93 |
| CTR ratchet, SHA3-256 | 19.79 | 197,358 | 48.18 | 125.09 |
| CBC ratchet, SHA3-256 | 19.90 | 196,316 | 47.93 | 124.43 |

- `cycles/byte` means total timestamp-counter cycles divided by total bytes processed. It is a processor-work measure for this host, not a portable duration or a literal count for one byte.
- Manual block-by-block XTS is about 2.9 to 3.0 times faster than AES-ratcheted CTR/CBC and about 5.5 times faster than BLAKE3-ratcheted CTR/CBC in this run.
- CTR and CBC variants with the same evolution function have similar throughput. The serial ratchet transition, not the choice between the two data equations, dominates.
- The OpenSSL full-sector XTS control demonstrates the benefit of batching and optimized library internals. It must not be used to claim that the manual XTS equations themselves are 9 times faster.
- Across the tested sector and volume sizes, total work remains linear in processed bytes. Larger volumes mainly stabilize fixed setup and timing noise rather than change complexity.

### RQ3 answer: hash-function choice

| Evolution primitive | ns/update | cycles/update | Relative to AES evolution | 4096-byte CTR MiB/s |
|---|---:|---:|---:|---:|
| AES-256 | 22.79 | 59.18 | 1.00x | 117.16 |
| BLAKE3 | 128.47 | 333.52 | 5.64x | 64.45 |
| SHA-256 | 270.93 | 703.37 | 11.89x | 38.54 |
| BLAKE2s-256 | 390.01 | 1,012.52 | 17.11x | 28.99 |
| SHA3-256 | 595.34 | 1,545.58 | 26.12x | 19.79 |

- AES is the fastest state-evolution primitive on this AES-NI-capable host.
- BLAKE3 is the fastest tested hash. It is about 2.1 times faster than SHA-256, 3.0 times faster than BLAKE2s-256, and 4.6 times faster than SHA3-256 for this 48-byte dependent input.
- The initial assumption that BLAKE3 would be about six times slower than AES is supported: this run measured 5.64x at the isolated update level.
- BLAKE2s and SHA3 are secure candidates, but neither is a performance improvement over BLAKE3 in this implementation. Their presence strengthens RQ3 by showing that the result is measured rather than assumed.
- These are implementation results, not universal hash rankings. BLAKE3 is compiled in portable mode, while OpenSSL and AES may use host-specific acceleration.

### RQ4 answer: random access and parallel recovery

Warm-cache median target-recovery latency is:

| Construction | Block 1 | Block 256 | Why it grows or stays flat |
|---|---:|---:|---|
| AES-ECB | 40 ns | 40 ns | Independent block |
| AES-XTS manual | 70 ns | 1,051 ns | Current target path advances the public tweak from `T0` |
| CTR ratchet, AES | 140 ns | 5,388 ns | Replays preceding ciphertext-dependent states |
| CBC ratchet, AES | 150 ns | 5,398 ns | Replays preceding ciphertext-dependent states |
| CTR ratchet, BLAKE3 | 160 ns | 31,026 ns | Replays a slower hash transition |
| CBC ratchet, BLAKE3 | 161 ns | 31,026 ns | Replays a slower hash transition |

- ECB target cost is constant. Ratcheted target cost is `O(j)` because recovering block `j` requires rebuilding every prior state in that sector.
- XTS does not have the ratchet dependency. The measured manual helper is `O(j)` only because it literally advances `T0` to the requested index. An implementation can compute or precompute the public XTS mask independently of prior ciphertext, so this timing must not be presented as an inherent XTS random-access limitation.
- Warm means data and code are likely cache-resident. Cache-thrashed rows and standard deviations remain in the CSV for a less optimistic view.

At 9 threads on the 9-logical-CPU allocation:

| Construction | 1-thread MiB/s | 9-thread MiB/s | Speedup `S(9)` | Efficiency `E(9)` |
|---|---:|---:|---:|---:|
| AES-XTS manual | 340.28 | 1,855.44 | 5.45x | 60.59% |
| OpenSSL full-sector XTS | 2,893.08 | 7,270.39 | 2.51x | 27.92% |
| CTR ratchet, AES | 110.85 | 754.04 | 6.80x | 75.58% |
| CBC ratchet, AES | 121.46 | 622.24 | 5.12x | 56.92% |
| CTR ratchet, BLAKE3 | 63.11 | 365.27 | 5.79x | 64.31% |
| CBC ratchet, BLAKE3 | 63.54 | 365.49 | 5.75x | 63.91% |

- Sector-level independence recovers substantial aggregate throughput even though blocks within one ratcheted sector remain serial.
- AES CTR ratcheting showed the strongest endpoint scaling at 6.80x and 75.58% efficiency. BLAKE3 CTR/CBC reached about 5.8x and 64% efficiency.
- The full thread-by-thread graph is more informative than the endpoint table because this virtualized host has non-monotonic steps and shared-resource contention.
- BLAKE2s, SHA3, and SHA-256 variants scaled poorly beyond a few threads in this run. That result cannot safely be attributed to the algorithms alone; OpenSSL provider behavior, CPU allocation, frequency changes, and memory contention require profiling before a causal claim.

## 5. Interesting questions and further consideration

- Repeat the benchmark on bare-metal machines with fixed CPU affinity, fixed frequency policy, and recorded physical-core versus logical-thread topology. This would separate ratchet costs from virtualization and scheduler noise.
- Compare the portable BLAKE3 build used here with its SIMD dispatch enabled. The present result is conservative for BLAKE3 and is not an optimized-library-versus-optimized-library comparison.
- Profile the low scaling of OpenSSL hash ratchets with hardware counters and provider-specific builds before deciding whether the bottleneck is hashing, EVP reset overhead, memory traffic, or host contention.
- Implement an XTS random-target helper using direct finite-field exponentiation or a precomputed per-sector tweak table. This will make the structural difference between public position masks and ciphertext-dependent ratchet states explicit.
- Extend the benchmark to actual block-device I/O only after the in-memory results are stable. Report crypto-only time separately from queueing, filesystem, cache, and device latency.
- Evaluate authenticated designs and crash-consistent metadata. The current four constructions measure confidentiality mechanics only and do not provide sector integrity or rollback protection.
- The extra hash candidates are standardized or publicly specified and are not known to be practically broken: [BLAKE2 specification](https://www.blake2.net/), [NIST SHA-3 FIPS 202](https://csrc.nist.gov/pubs/fips/202/final), and [NIST Secure Hash Standard FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final).
