# In-memory ratcheted FDE implementation and benchmark

## Project status

- This repository is a reproducible, in-memory implementation of the revised Task 9 V0.2 pseudocode for AES-ECB, AES-XTS, CTR ratcheting, and the construction named CBC ratcheting in Task 9.
- The BLAKE3 alternatives are included because both the updated PDF and the supplied ZIP contain them, so the benchmark has six Task 9 variants plus an optimized OpenSSL XTS reference.
- Disk I/O is intentionally excluded, as requested, and every reported measurement is a cryptographic CPU and memory measurement rather than a storage-system result.
- The code is a research prototype and not a deployable FDE system because it uses deterministic test keys, provides no authentication or integrity protection, does not erase all sensitive state explicitly, and has not received an independent security audit.
- The name `Ratchet-CBC` is retained to match Task 9, but the construction is not conventional CBC: it encrypts each plaintext block under the current ratcheted key and does not XOR the previous ciphertext into the next plaintext.

## Task 9 conformance decisions

- AES-ECB computes `C[j] = AES-256(K, P[j])` and deliberately ignores the sector number and index vector.
- AES-XTS computes `T0 = AES-256(K2, S)` and `C[j] = AES-256(K1, P[j] XOR (T0 * alpha^I[j])) XOR (T0 * alpha^I[j])` using the IEEE P1619 little-endian polynomial convention.
- Consecutive XTS indices use the equivalent recurrence `T[j+1] = MUL_ALPHA(T[j])`, while `fde_xts_encrypt_indexed` and `fde_xts_decrypt_indexed` preserve the literal Task 9 formula for arbitrary index vectors.
- The recurrence optimization is algebraic, not an endianness workaround: starting at `I[0] = 0`, one multiplication produces the tweak for index 1, two produce the tweak for index 2, and so on.
- Sector numbers are encoded as 64-bit little-endian values in a zero-padded 128-bit AES block, and indices are encoded as 32-bit little-endian values in a zero-padded 128-bit AES block, avoiding the supplied code's host-endian `memcpy` behavior.
- Every tested sector is an exact multiple of the 16-byte AES block size, matching Task 9's block-vector model, so ciphertext stealing for a partial final XTS block is outside this prototype's scope.
- CTR-AES computes `C[j] = P[j] XOR AES-128(K[j-1], I[j])`, then `K[j] = AES-256(KG, K[j-1] XOR C[j])`.
- CBC-AES computes `C[j] = AES-128(K[j-1], P[j])`, then applies the same AES-256 ratchet transition.
- CTR-BLAKE3 and CBC-BLAKE3 compute `K[j] = BLAKE3(K[j-1] || C[j])` as the specified unkeyed 48-byte one-shot hash.
- Task 9 declares 256-bit master keys but obtains the initial ratchet state from a 128-bit AES block, so its types do not permit every `AES.Enc(K, ...)` call to remain AES-256 without an extra, unspecified expansion rule.
- The implementation resolves that ambiguity exactly as the supplied ZIP does: AES-ratchet state is 128 bits and therefore drives AES-128, while a BLAKE3 state is 256 bits and drives AES-256; the 128-bit AES seed is zero-extended for the first BLAKE3-state use.
- That width decision is explicit in the code and should be confirmed with the mentor before treating the constructions as final cryptographic specifications.

## Audit of the supplied ZIP

- All six supplied C sources recompiled and completed their own encrypt/decrypt round-trip checks, so the ZIP was a workable functional basis.
- The prebuilt files in the ZIP are Mach-O executables and therefore do not run directly on Linux; this repository builds native executables from source instead.
- A round trip alone can validate invertibility while missing a wrong convention, so the new tests also compare the manual AES-XTS ciphertext byte-for-byte with OpenSSL AES-256-XTS.
- The supplied AES helper allocated, initialized, and destroyed an OpenSSL cipher context for every 16-byte AES call, causing context management and key setup to dominate the measured algorithms.
- The new implementation creates persistent worker contexts once, reuses fixed-key AES schedules, and rekeys only the dynamic-key contexts whose ratchet key genuinely changes per block.
- The supplied XTS benchmark reset `T` to `T0` and repeated `I[j]` multiplications for every sequential block, which takes `0 + 1 + ... + (n-1) = O(n^2)` tweak operations for a sector.
- The new fair XTS baseline uses `n-1 = O(n)` multiplications for sequential indices, retains a separate literal indexed function for conformance experiments, and includes OpenSSL's full-sector AES-XTS only as an optimized production reference.
- The supplied code used native-endian memory copies for `S` and `I[j]`; the new implementation uses stable little-endian encodings and consequently produces the same values on different host architectures.
- The official BLAKE3 v1.8.7 portable sources from the supplied ZIP are vendored unchanged and pass the official empty-input digest test.
- The supplied ZIP did not include BLAKE3 SIMD implementation files, so this repository deliberately disables those dispatch paths rather than pretending that portable BLAKE3 is the fastest possible BLAKE3 implementation.

## Repository layout

- `include/fde.h` exposes the six construction APIs, exact indexed XTS, OpenSSL XTS, target-block recovery, and isolated ratchet transitions.
- `src/fde.c` contains the cryptographic implementation with persistent OpenSSL EVP contexts.
- `src/benchmark.c` contains independently callable RQ1, RQ2, RQ3, and RQ4 benchmark functions selected by command-line options.
- `tests/test_fde.c` contains the correctness, interoperability, index-semantics, and target-recovery checks.
- `third_party/blake3` contains the portable BLAKE3 C files supplied with the original project.
- `results` contains the full CSV measurements and environment metadata reported below.
- `scripts/run_all.sh` rebuilds, tests, sanitizes, captures the environment, and runs the complete benchmark.

## Downloading and running in VS Code

- Download and extract `fde-ratchet-bench.zip`, then open the extracted `fde-ratchet-bench` folder in VS Code rather than opening an individual C file.
- On Ubuntu or VS Code with WSL, install the build dependencies with `sudo apt update && sudo apt install build-essential pkg-config libssl-dev`.
- On macOS, install the command-line tools, `pkg-config`, and OpenSSL 3, for example with `xcode-select --install` and `brew install pkg-config openssl@3`.
- On Windows, the recommended reproducible route is VS Code's WSL extension with an Ubuntu distribution, because the Makefile and monotonic-clock benchmark target POSIX systems.
- The Microsoft C/C++ VS Code extension is useful for navigation and debugging but is not required by the command-line build.
- Run `make clean && make test` in the VS Code integrated terminal to compile and execute the correctness suite.
- Run `make sanitize` to execute AddressSanitizer and UndefinedBehaviorSanitizer checks; leak detection is excluded from this target because it is unavailable under some traced containers, while `make sanitize-leaks` enables it on a normal host.
- Run `./build/fde_bench --quick results_quick` after `make all` for a short smoke benchmark.
- Run `./build/fde_bench --rq1 results_rq1`, `--rq2 results_rq2`, `--rq3 results_rq3`, or `--rq4 results_rq4` to investigate one research question independently.
- Run `./scripts/run_all.sh` for the full reproducible workflow, which takes longer and replaces the CSV files in `results`.
- Expect the qualitative ordering and linear trends below on a modern AES-accelerated x86-64 machine, but do not expect identical absolute times because CPU model, frequency, OpenSSL provider, thermal state, virtualization, and background load all affect microbenchmarks.

## Correctness and validation results

- All six constructions round-trip correctly at both 512-byte and 4096-byte sector sizes.
- Manual sequential XTS equals the literal indexed Task 9 formula for consecutive indices.
- Manual AES-256-XTS equals OpenSSL AES-256-XTS byte-for-byte for complete sectors, confirming the tweak multiplication, sector encoding, key order, and encrypt/decrypt equations together.
- Exact indexed XTS round-trips a shuffled arbitrary index vector, as required by the Task 9 footnote that tuple position `j` need not equal index value `I[j]`.
- CTR ratcheting changes when `I[j]` changes, while CBC ratcheting ignores `I[j]` exactly as the pseudocode specifies.
- Every construction recovers target blocks 1, 32, 64, 128, 192, and 256 correctly in the RQ4 path.
- The vendored BLAKE3 implementation passes its official empty-input known-answer test.
- AddressSanitizer and UndefinedBehaviorSanitizer report no fault in the complete correctness suite in this environment.

## Benchmark method

- The included full run used Linux 6.18 on an AMD EPYC 9V74 host allocation with 9 visible logical CPUs, GCC 13.3.0, and OpenSSL 3.0.13.
- RQ1 instruments 500 encryptions and 500 decryptions of a 4096-byte sector and reports seed, data-path, and state-evolution shares.
- RQ2 measures both 1 MiB and 32 MiB volumes, 512-byte and 4096-byte sectors, encryption and decryption, with five trials per point.
- RQ2 reports mean and median throughput, mean nanoseconds per sector, standard deviation, and TSC cycles per byte when the x86 time-stamp counter is available.
- The input is deterministic arbitrary binary data, cipher contexts are created outside timed trials, and a warm-up encryption occurs before measurement.
- OpenSSL full-sector XTS is reported separately because one EVP call over an entire sector can use optimized internal batching, while the manual construction and ratchets must expose individual block and key-evolution operations.
- RQ3 measures one million sequential AES and BLAKE3 ratchet updates and also uses the RQ2 end-to-end rows for the four ratchet constructions.
- RQ4 randomizes target order, reports 1000 warm samples and 80 cache-thrashed samples per target, and verifies the recovered plaintext during every sample.
- RQ4 scaling encrypts 64 MiB of independent 4096-byte sectors using 1, 2, 4, and 8 threads; a start gate excludes thread and worker creation from timed work.
- The component timer adds measurement overhead at every block boundary, so component percentages answer where instrumented time is spent but the outer wall-clock and RQ2 measurements are the authoritative end-to-end times.

## RQ1: Where does encryption and decryption time go?

| Construction, 4096-byte encryption | Seed | AES data path | Tweak or ratchet evolution |
|---|---:|---:|---:|
| AES-ECB | 0.00% | 100.00% | 0.00% |
| AES-XTS manual sequential | 0.27% | 55.97% | 43.76% |
| Ratchet-CTR-AES | 0.11% | 70.47% | 29.43% |
| Ratchet-CTR-BLAKE3 | 0.07% | 45.86% | 54.07% |
| Ratchet-CBC-AES | 0.12% | 76.16% | 23.72% |
| Ratchet-CBC-BLAKE3 | 0.07% | 48.82% | 51.11% |

- Sector seeding is negligible because it is one AES call amortized across 256 blocks.
- AES ratchet generation consumes about 24% to 29% of instrumented encryption time, while portable one-shot BLAKE3 consumes about 51% to 54%.
- Decryption has the same overall split: AES evolution consumes 29.26% for CTR and 22.62% for CBC, while BLAKE3 evolution consumes 53.22% for CTR and 49.09% for CBC.
- The manual XTS `MUL_ALPHA` loop is cheap in absolute terms but accounts for about 44% of finely instrumented block-level time because each AES data call is hardware accelerated.
- Literal indexed XTS spends 93.09% of instrumented time recomputing powers and takes 79.3 ms for 500 sectors, versus 14.9 ms for the equivalent sequential recurrence, demonstrating why the literal loop must not be used as the normal sequential benchmark.
- For `n` blocks, ECB, efficient sequential XTS, and both ratchets perform `O(n)` cryptographic work, while the literal repeated-loop XTS implementation is `O(sum I[j])` and becomes `O(n^2)` only when `I[j] = j`.

## RQ2: Throughput, latency, sector size, and volume

| 32 MiB encryption, 4096-byte sectors | Mean MiB/s | Mean ns/sector | Mean cycles/byte |
|---|---:|---:|---:|
| AES-ECB | 939.09 | 4,159.60 | 2.64 |
| AES-XTS manual sequential | 342.12 | 11,417.70 | 7.24 |
| AES-XTS OpenSSL full-sector reference | 3,332.03 | 1,172.34 | 0.74 |
| Ratchet-CTR-AES | 115.00 | 33,967.51 | 21.53 |
| Ratchet-CTR-BLAKE3 | 65.09 | 60,009.60 | 38.03 |
| Ratchet-CBC-AES | 125.95 | 31,013.07 | 19.66 |
| Ratchet-CBC-BLAKE3 | 68.34 | 57,158.79 | 36.23 |

- The manual per-block XTS baseline is 2.97 times faster than CTR-AES and 2.72 times faster than CBC-AES at 4096 bytes, while the portable BLAKE3 ratchets are about five times slower than manual XTS.
- OpenSSL full-sector XTS reaches 3,332 MiB/s, or about 3.25 GiB/s, because it amortizes EVP overhead and exploits optimized AES-XTS internals, so it is a useful production ceiling but not evidence that the XTS formula itself is ten times cheaper than the manual XTS formula.
- Ratchet throughput changes little between 512-byte and 4096-byte sectors at 32 MiB: CTR-AES rises from 110.77 to 115.00 MiB/s, CBC-AES remains near 126 MiB/s, CTR-BLAKE3 rises from 63.21 to 65.09 MiB/s, and CBC-BLAKE3 rises from 65.29 to 68.34 MiB/s.
- Ratchet throughput also remains broadly stable from 1 MiB to 32 MiB, which agrees with linear `Theta(n)` evolution and shows that the per-sector seed is already well amortized at 512 bytes.
- The corresponding 32 MiB decryption rates at 4096 bytes are 340.23 MiB/s for manual XTS, 118.73 MiB/s for CTR-AES, 61.71 MiB/s for CTR-BLAKE3, 123.08 MiB/s for CBC-AES, and 64.42 MiB/s for CBC-BLAKE3, so encryption and decryption lead to the same comparative conclusion.
- Increasing a sector from 512 to 4096 bytes increases ratchet latency by about eight times because the block chain is eight times longer; it does not change the linear complexity class.
- OpenSSL XTS benefits strongly from the larger sector API call, rising from 828.43 MiB/s at 512 bytes to 3332.03 MiB/s at 4096 bytes, which is precisely why it is kept separate from the block-granular comparison.

## RQ3: AES versus BLAKE3 ratchet evolution

| Sequential state transition | ns/update | TSC cycles/update |
|---|---:|---:|
| AES-256(`KG`, `K XOR C`) | 20.99 | 54.50 |
| Portable BLAKE3(`K || C`), 48-byte input | 123.50 | 320.62 |

- On this AES-accelerated host, the isolated AES control is 5.88 times faster per update than the supplied portable BLAKE3 path.
- End-to-end at 32 MiB and 4096-byte sectors, CTR-AES reaches 115.00 MiB/s versus 65.09 MiB/s for CTR-BLAKE3, and CBC-AES reaches 125.95 MiB/s versus 68.34 MiB/s for CBC-BLAKE3.
- These data answer the implemented AES-control-versus-BLAKE3 choice, but they do not establish which hash function is best because the supplied project implements only one actual hash function.
- A defensible multi-hash answer would add BLAKE2s, SHA3-256, and SHA-256 under the same fixed 48-byte one-shot interface, while a defensible optimized-BLAKE3 answer would also build the official SIMD source files absent from the supplied ZIP.
- Bulk-hash marketing throughput is not the relevant number here because each ratchet step hashes one short 48-byte message and cannot batch subsequent steps within a sector.
- No disk conclusion is claimed for RQ3 because disk was deliberately excluded; storage latency could hide much of the CPU difference and must be measured in the later disk phase.

## RQ4: Random access and sector-level parallelism

| Warm target recovery | Median at block 1 | Median at block 256 |
|---|---:|---:|
| AES-ECB | 40 ns | 40 ns |
| AES-XTS manual | 70 ns | 1,051 ns |
| Ratchet-CTR-AES | 141 ns | 5,388 ns |
| Ratchet-CTR-BLAKE3 | 150 ns | 29,164 ns |
| Ratchet-CBC-AES | 150 ns | 5,398 ns |
| Ratchet-CBC-BLAKE3 | 160 ns | 29,174 ns |

- ECB directly decrypts the selected ciphertext block and is position independent.
- XTS also requires no earlier ciphertext; this implementation derives `T0 * alpha^I[j]` with public tweak multiplications, so its measured cost grows mildly with the public index but remains about 1.05 microseconds at block 256.
- A precomputed per-sector tweak table or a jump-ahead field-multiplication routine could flatten XTS's computational index cost, while neither optimization can remove a ratchet's dependence on preceding ciphertext.
- AES ratchets must replay 255 state transitions before recovering block 256 and take about 5.4 microseconds, while portable BLAKE3 ratchets take about 29.2 microseconds.
- The near-linear target trend is the intended cost of ciphertext-dependent ratcheting: block `j` requires the seed plus `j-1` prior state transitions, even if the storage system has already loaded the whole sector.
- Cache-thrashed medians preserve the same ordering, and the CSV retains mean, median, and standard deviation because hosted-system interruptions create visible outliers in some mean values.

| 64 MiB, 4096-byte sectors, 8 threads | 1-thread MiB/s | 8-thread MiB/s | Speedup | Efficiency |
|---|---:|---:|---:|---:|
| AES-XTS manual sequential | 345.47 | 2,091.92 | 6.06x | 75.69% |
| Ratchet-CTR-AES | 108.28 | 599.85 | 5.54x | 69.25% |
| Ratchet-CTR-BLAKE3 | 63.24 | 323.72 | 5.12x | 63.98% |
| Ratchet-CBC-AES | 126.70 | 647.51 | 5.11x | 63.88% |
| Ratchet-CBC-BLAKE3 | 66.65 | 405.35 | 6.08x | 76.02% |

- Ratcheting prevents useful intra-sector parallelism because `K[j]` depends on `C[j]`, but independent sector seeds permit different sectors to be processed concurrently.
- Eight threads recover between 5.11x and 6.08x throughput for the four ratchets on this 9-logical-CPU allocation, demonstrating substantial but non-ideal recovery through sector-level independence.
- Efficiency falls at higher thread counts because of scheduling, shared-cache and memory pressure, virtualized CPU capacity, and per-thread OpenSSL overhead.
- OpenSSL full-sector XTS already reaches 3,193 MiB/s, or about 3.12 GiB/s, with one thread and scales only 2.38x at eight threads in this run, which is consistent with earlier saturation of shared hardware resources.

## Answers suitable for mentor discussion

- RQ1 is answered by showing that AES-based ratchets spend roughly one quarter of instrumented time on evolution, whereas the supplied portable BLAKE3 update consumes roughly half, with the seed cost effectively disappearing after amortization.
- RQ2 is answered by showing linear work in the number of 128-bit blocks, broadly volume-independent throughput, and sector latency proportional to block count, with AES ratchets around 115 to 126 MiB/s and portable BLAKE3 ratchets around 65 to 68 MiB/s in the representative 32 MiB run.
- RQ3 is only partially answered: AES is the faster implemented state transition on this AES-accelerated machine, but BLAKE3 cannot be declared the best or worst hash without optimized SIMD and additional hash candidates.
- RQ4 is answered by quantifying the trade: ratcheting loses direct intra-sector access and reaches a later block by replaying the chain, but sector-level parallelism recovers roughly fivefold to sixfold throughput at eight threads.
- The strongest implementation lesson is that a literal pseudocode loop can accidentally turn sequential XTS into an `O(n^2)` benchmark, so performance claims must distinguish semantic equivalence, implementation granularity, and library batching.
- The strongest specification question for the mentor is the ratchet key width: a 128-bit AES output cannot silently become a 256-bit AES key, and the current zero-extension rule for the BLAKE3 branch is inherited from the supplied basis rather than derived from a formal key-derivation specification.
- The next experimental step should freeze that key-width rule, add optimized BLAKE3 and other hash candidates if RQ3 remains in scope, pin benchmark threads to physical cores, increase independent run counts, and only then extend the same API to real disk I/O.

## Result files

- `results/throughput.csv` contains every RQ2 sector-size, volume, operation, throughput, latency, variation, and cycles-per-byte measurement.
- `results/component_breakdown.csv` contains the RQ1 seed, data-path, and evolution measurements, including the deliberately inefficient literal indexed XTS control.
- `results/ratchet_primitives.csv` contains the RQ3 million-update AES and BLAKE3 controls.
- `results/random_access.csv` contains all RQ4 warm and cache-thrashed target distributions.
- `results/parallel_scaling.csv` contains all RQ4 thread counts, throughput, speedup, and efficiency values.
- `results/environment.txt` and `results/run_metadata.txt` identify the run environment and selected profile.

## Reproducibility limitations

- The benchmark reports one hosted environment rather than a population of machines, so its exact nanosecond and MiB/s values are not universal performance guarantees.
- CPU affinity and frequency were not controlled, and occasional hosted-system interruptions are visible in some standard deviations; medians should be consulted alongside means.
- TSC cycles per byte are useful within this x86 run but may reflect a virtualized or invariant reference clock rather than current core cycles.
- The BLAKE3 result measures the portable implementation supplied by the user, not an AVX2 or AVX-512 build.
- The test data fit in memory and do not include filesystem, block layer, device queue, DMA, caching, or persistence effects.
- The benchmark establishes functional correctness and implementation cost only; it does not prove confidentiality, integrity, misuse resistance, crash consistency, or secure key management.
