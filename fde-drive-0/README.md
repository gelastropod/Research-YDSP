# Ratcheted FDE Implementation on hard drive

See [fde-c-3](/fde-c-3/)

## Building and running

This program only works on Linux systems.

Run `make test-drive` to build the files.

To use the program (`build/fde_test_drive`) to encrypt/decrypt a drive, first connect the drive and find where it is located (say `/dev/sda`), then run the following:
```
build/fde_test_drive [--scheme <name>] <encrypt/decrypt> <device> [offset_bytes] [count_bytes] [csv_path] [direct]
```
`--scheme` (or `-s`) picks the encryption scheme: `ecb`, `xts`, `ctr-aes` (default), `ctr-blake3`, `cbc-aes`, `cbc-blake3` or `xex-sha3` (full names such as `Ratchet-CBC-AES` also work). With `make test-drive`, pass `DRIVE_SCHEME=<name>`. Decrypt with the same scheme used to encrypt.

So to encrypt the entire drive in `/dev/sda` for example (without buffering, using O_DIRECT flag), and write the timing data into `results/drive_throughput.csv`, run
```
build/fde_test_drive encrypt /dev/sda 0 0 results/drive_throughput.csv direct
```

## Running multiple schemes

`scripts/run_drive_schemes.sh` runs the drive test once per scheme, producing the same console output and a per-scheme CSV (`results/drive_<mode>_<scheme>.csv`, identical columns to `drive_throughput.csv`):

```
sh scripts/run_drive_schemes.sh <encrypt/decrypt> <device> [offset_bytes] [count_bytes] [--schemes "ecb xts ..."|all] [--results-dir DIR] [--direct]
```

`--schemes` accepts a space- or comma-separated list of the scheme aliases above, or `all` (the default). A failing scheme is reported and the run continues with the rest.

Equivalent make target (builds the binary first):

```
make test-drive-schemes DRIVE_DEVICE=/dev/sda DRIVE_MODE=encrypt \
    DRIVE_SCHEMES="ecb xts ctr-aes" DRIVE_DIRECT=--direct
```

`DRIVE_SCHEMES=all` (default) runs every scheme. To compare the resulting CSVs in one figure, pass them all to the plot script:

```
python scripts/plot_drive_throughput.py results/drive_encrypt_*.csv -o figures/schemes_throughput.png
```

## Preliminary testing and results

**Setup:** 128 GB device, 4 KB sectors (31.26M sectors), `O_DIRECT` with 1 MB batched I/O, per-sector crypto.

### Key takeaways

1. **The ratchet costs roughly 30% of drive throughput with AES and about 45% with BLAKE3,** compared with AES-XTS: 61 / 47 MB/s vs 86 MB/s when encrypting a 1 GiB drive.
2. **The ratchet primitive sets the cost.** One AES-256 update takes 16.2 ns, while one BLAKE3 update takes 96.9 ns (about 6x slower). The random-access latencies match these per-update costs almost exactly.
3. **CTR and CBC ratchet modes perform the same.** The two modes are within about 1–5% of each other in every test, so the choice of primitive matters and the choice of mode does not.
4. **Random access within a sector costs O(block index) for ratcheted schemes.** Reaching block 256 takes about 4.3 µs with AES and about 24 µs with BLAKE3. ECB stays flat at about 107 ns.
5. **On a real drive, part of the CPU gap is hidden by I/O.** In memory the ratchet is about 5x slower than manual XTS, but on the drive it is only about 1.4x slower, because disk I/O takes 34% of wall time.
6. **The ratchet parallelizes well across sectors,** reaching about 5.5x at 8 threads, which is better than OpenSSL XTS (3.0x, limited by memory bandwidth).

### 1. Ratchet primitive cost (`ratchet_primitives.csv`)

| Primitive | ns / update | TSC cycles / update |
|---|---|---|
| AES-256(K_G, K ⊕ C) | 16.2 | 61.5 |
| BLAKE3(K ‖ C) | 96.9 | 367.4 |

BLAKE3 is about **6.0x** more expensive for each update.

### 2. Per-sector component breakdown (`component_breakdown.csv`, 500 iterations)

| Implementation | Op | µs / sector (outer) | Data % | Evolution % |
|---|---|---|---|---|
| AES-ECB | enc | 12.3 | 100 | 0 |
| AES-XTS-manual | enc | 22.2 | 61.8 | 37.9 |
| Ratchet-CTR-AES | enc | 41.8 | 76.1 | 23.8 |
| Ratchet-CBC-AES | enc / dec | 41.3 / 43.0 | 75.5 / 76.9 | 24.4 / 23.0 |
| Ratchet-CTR-BLAKE3 | enc | 62.0 | 48.4 | 51.6 |
| Ratchet-CBC-BLAKE3 | enc / dec | 61.8 / 63.5 | 48.0 / 49.7 | 51.9 / 50.2 |
| AES-XTS-literal-indexed | enc | 193.1 | 4.2 | **95.8** |

- Seed derivation is negligible (under 0.3%).
- In the AES ratchets, the data path dominates (about 76%). In the BLAKE3 ratchets, key evolution takes about half of the time.
- In "literal-indexed" XTS, which recomputes the tweak from the index for every block, 96% of the time goes to tweak evolution. It is 8.7x slower than incremental XTS.
- Decryption costs the same as encryption, except CBC decrypt, which is about 2–4% slower.

### 3. Random access within a sector (`random_access.csv`, latency to reach block *k*)

Mean latency in ns (warm cache):

| Scheme | k=1 | k=32 | k=64 | k=128 | k=256 | ≈ ns / block |
|---|---|---|---|---|---|---|
| AES-ECB | 107 | 107 | 107 | 107 | 107 | 0 (O(1)) |
| AES-XTS-manual | 56 | 192 | 354 | 671 | 1,328 | ~5.0 |
| Ratchet-CTR-AES | 122 | 629 | 1,155 | 2,202 | 4,307 | ~16.4 |
| Ratchet-CBC-AES | 124 | 633 | 1,160 | 2,214 | 4,308 | ~16.4 |
| Ratchet-CTR-BLAKE3 | 123 | 3,100 | 6,149 | 12,249 | 24,488 | ~95.5 |
| Ratchet-CBC-BLAKE3 | 132 | 3,019 | 5,988 | 11,897 | 23,743 | ~93 |

- The latency grows linearly with *k*. The per-block slope matches the primitive costs in Section 1 (16.2 ns for AES, 96.9 ns for BLAKE3).
- **Cache-thrashed** runs (80 samples) add a roughly constant **200–350 ns**, mostly visible at small *k*, and have higher variance. The slope is unchanged.

### 4. Parallel scaling (`parallel_scaling.csv`, 64 MiB volume, 3 trials)

| Implementation | 1 thread (MiB/s) | 8 threads (MiB/s) | Speedup @8 | Efficiency @8 |
|---|---|---|---|---|
| AES-ECB | 1,071 | 5,014 | 4.68x | 0.59 |
| AES-XTS-manual | 729 | 4,467 | 6.13x | 0.77 |
| AES-XTS-OpenSSL (full sector) | 3,897 | 11,739 | 3.01x | 0.38 |
| Ratchet-CTR-AES | 144 | 814 | 5.65x | 0.71 |
| Ratchet-CBC-AES | 136 | 746 | 5.48x | 0.68 |
| Ratchet-CTR-BLAKE3 | 83.6 | 472 | 5.64x | 0.71 |
| Ratchet-CBC-BLAKE3 | 87.2 | 456 | 5.23x | 0.65 |

- Up to 4 threads, all schemes scale almost linearly (efficiency of at least 0.86), except OpenSSL XTS (0.64 at 4 threads).
- OpenSSL XTS and ECB are memory-bound at 8 threads. The ratchets are compute-bound, so they keep scaling.
- Single-threaded, Ratchet-AES is about 27x slower than OpenSSL XTS and about 5x slower than manual XTS.

### 5. Full-drive encryption, 1 GiB (`drive_encrypt_*.csv`, 262,144 sectors)

| Scheme | Time (s) | Avg MB/s | vs XTS | Data % | Evolution % | Disk I/O % | Other % |
|---|---|---|---|---|---|---|---|
| ECB | 9.83 | **109.3** | 1.27x | 24.2 | 0 | 60.4 | 15.4 |
| XTS | 12.45 | **86.2** | 1.00x | 18.5 | 11.8 | 47.1 | 22.5 |
| Ratchet-CBC-AES | 17.47 | **61.5** | 0.71x | 38.8 | 12.1 | 33.9 | 15.2 |
| Ratchet-CTR-AES | 17.64 | **60.9** | 0.71x | 39.3 | 12.0 | 33.7 | 15.0 |
| Ratchet-CBC-BLAKE3 | 22.85 | **47.0** | 0.55x | 30.2 | 32.5 | 25.8 | 11.4 |
| Ratchet-CTR-BLAKE3 | 22.86 | **47.0** | 0.54x | 30.5 | 32.7 | 25.3 | 11.4 |
| XEX-SHA3 | 41.18 | **26.1** | 0.30x | 5.2 | **74.3** | 14.2 | 6.3 |

- Throughput is steady across each run. For example, Ratchet-AES varies between 49 and 66 MB/s instantaneous and XTS between 65 and 94 MB/s.
- As the cipher gets cheaper, disk I/O takes a larger share of the time: 14% for XEX-SHA3, 34% for Ratchet-AES, and 60% for ECB. ECB is mostly I/O-bound.
- XEX-SHA3 is the slowest scheme by far, because SHA-3 tweak evolution takes three quarters of its wall time.

`drive_throughput.csv` is a shorter 100 MB ratcheted run: 40.8 MB/s average, with disk I/O at 56% of wall time.

### 6. Long-run ratcheted AES-XTS drive test (`throughput_plot.png`, about 128 GB)

- **0–3% of the device:** about 63 MB/s, with I/O at about 33% of wall time.
- **3–65%:** about 49 MB/s, with regular dips to about 38 MB/s roughly every 3–5%. I/O rises to about 50%, with spikes at the dips.
- **65–100%:** a step down to about 37 MB/s, with I/O at about 60%. After about 90%, frequent drops to about 8–10 MB/s appear, with I/O spikes up to about 90%.
- The cumulative average ends at about **42 MB/s**.
- The CPU side should be constant per sector. Every step and dip comes with a rise in the I/O share, so the degradation looks like it comes from the drive and not the cipher. Likely causes are SSD write-cache exhaustion or thermal throttling, but this is an inference I have not verified.
