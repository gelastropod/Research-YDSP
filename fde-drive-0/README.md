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

1. **The ratchet costs roughly 30% of drive throughput with AES and about 45% with BLAKE3,** compared with AES-XTS: 61 / 46 MB/s vs 86 MB/s when encrypting a 1 GiB drive.
2. **The ratchet primitive sets the cost.** One AES-256 update takes 16.2 ns, while one BLAKE3 update takes 96.9 ns (about 6x slower). The random-access latencies match these per-update costs almost exactly.
3. **CTR and CBC ratchet modes perform the same.** The two modes are within about 1–5% of each other in every test, so the choice of primitive matters and the choice of mode does not.
4. **Decryption costs the same as encryption.** The only exception is CBC decrypt, which is about 2–4% slower.
5. **Among the XEX tweak hashes, SipHash is the fastest** (65 MB/s, 0.76x XTS) and slightly beats Ratchet-AES. KMAC is the slowest (16 MB/s, 0.19x XTS).
6. **Random access within a sector costs O(block index) for ratcheted schemes.** Reaching block 256 takes about 4.3 µs with AES and about 24 µs with BLAKE3. ECB stays flat at about 107 ns.
7. **The ratchet parallelizes well across sectors,** reaching about 5.5x at 8 threads, which is better than OpenSSL XTS (3.0x, limited by memory bandwidth).

### 1. Ratchet primitive cost (`ratchet_primitives.csv`)

| Primitive | ns / update | TSC cycles / update |
|---|---|---|
| Ratchet AES-256 | 20.7 | 78.7 |
| Ratchet BLAKE3 | 116.9 | 443.3 |
| XEX SHA3-256 (unkeyed) | 528.9 | 2006.0 |
| XEX BLAKE2b-MAC | 354.3 | 1343.7 |
| XEX keyed BLAKE3 | 115.9 | 439.7 |
| XEX SipHash-2-4-128 | 80.8 | 306.4 |
| XEX KMAC128 | 999.4 | 3790.6 |
| XTS tweak doubling | 11.1 | 42.1 |

- Per update: XTS doubling (11 ns) < Ratchet AES (21) < SipHash (81) < BLAKE3 ratchet ≈ keyed BLAKE3 (116) < BLAKE2b-MAC (354) < SHA3-256 (529) < KMAC128 (999).
- That is roughly a 90x spread between the cheapest and most expensive way to move the state forward.
- The ranking matches the drive throughput ranking exactly. Tweak/state evolution decides drive speed once disk I/O is taken out.

### 2. Per-sector component breakdown (`component_breakdown.csv`, 500 iterations)

<table>
  <tr><th>Implementation</th><th>Op</th><th>µs / sector</th><th>Data %</th><th>Evolution %</th><th>Seed %</th></tr>
  <tr><td rowspan="2">AES-ECB</td><td>enc</td><td>12.3</td><td>100.0</td><td>0.0</td><td>0.00</td></tr>
  <tr><td>dec</td><td>12.5</td><td>100.0</td><td>0.0</td><td>0.00</td></tr>
  <tr><td rowspan="2">AES-XTS-manual</td><td>enc</td><td>22.2</td><td>61.8</td><td>37.9</td><td>0.29</td></tr>
  <tr><td>dec</td><td>22.3</td><td>62.2</td><td>37.5</td><td>0.29</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-AES</td><td>enc</td><td>41.8</td><td>76.1</td><td>23.8</td><td>0.12</td></tr>
  <tr><td>dec</td><td>41.9</td><td>76.1</td><td>23.8</td><td>0.12</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-AES</td><td>enc</td><td>41.3</td><td>75.5</td><td>24.4</td><td>0.12</td></tr>
  <tr><td>dec</td><td>43.0</td><td>76.9</td><td>23.0</td><td>0.11</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-BLAKE3</td><td>enc</td><td>62.0</td><td>48.4</td><td>51.6</td><td>0.07</td></tr>
  <tr><td>dec</td><td>62.1</td><td>48.3</td><td>51.6</td><td>0.07</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-BLAKE3</td><td>enc</td><td>61.8</td><td>48.0</td><td>51.9</td><td>0.08</td></tr>
  <tr><td>dec</td><td>63.5</td><td>49.7</td><td>50.2</td><td>0.07</td></tr>
  <tr><td>AES-XTS-literal-indexed</td><td>enc</td><td>193.1</td><td>4.2</td><td><b>95.8</b></td><td>0.02</td></tr>
</table>

- Seed derivation is negligible (under 0.3%).
- In the AES ratchets, the data path dominates (about 76%). In the BLAKE3 ratchets, key evolution takes about half of the time.
- In "literal-indexed" XTS, which recomputes the tweak from the index for every block, 96% of the time goes to tweak evolution. It is 8.7x slower than incremental XTS. This file has an encrypt row only for this implementation.

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

### 5. Full-drive encryption, 1 GiB (`drive_encrypt_*.csv`, 262,144 sectors, encrypt only)

<table>
  <tr><th>Family</th><th>Scheme</th><th>Time (s)</th><th>Avg MB/s</th><th>vs XTS</th><th>Data %</th><th>Evolution %</th><th>Disk I/O %</th><th>Other %</th></tr>
  <tr><td rowspan="2">Baseline</td><td>ECB</td><td>10.31</td><td><b>104.2</b></td><td>1.22x</td><td>23.0</td><td>0.0</td><td>62.8</td><td>14.2</td></tr>
  <tr><td>XTS</td><td>12.55</td><td><b>85.5</b></td><td>1.00x</td><td>17.3</td><td>11.3</td><td>49.7</td><td>21.5</td></tr>
  <tr><td rowspan="2">Ratchet-AES</td><td>CTR</td><td>17.67</td><td><b>60.8</b></td><td>0.71x</td><td>37.9</td><td>11.6</td><td>35.8</td><td>14.6</td></tr>
  <tr><td>CBC</td><td>17.54</td><td><b>61.2</b></td><td>0.72x</td><td>37.3</td><td>11.9</td><td>35.9</td><td>14.8</td></tr>
  <tr><td rowspan="2">Ratchet-BLAKE3</td><td>CTR</td><td>23.45</td><td><b>45.8</b></td><td>0.54x</td><td>29.8</td><td>31.9</td><td>27.0</td><td>11.2</td></tr>
  <tr><td>CBC</td><td>23.37</td><td><b>45.9</b></td><td>0.54x</td><td>29.5</td><td>32.0</td><td>27.2</td><td>11.2</td></tr>
  <tr><td rowspan="5">XEX (hashed tweak)</td><td>SipHash</td><td>16.48</td><td><b>65.2</b></td><td>0.76x</td><td>12.7</td><td>33.0</td><td>38.4</td><td>15.9</td></tr>
  <tr><td>BLAKE3</td><td>18.51</td><td><b>58.0</b></td><td>0.68x</td><td>11.2</td><td>40.9</td><td>33.9</td><td>14.0</td></tr>
  <tr><td>BLAKE2b</td><td>32.37</td><td><b>33.2</b></td><td>0.39x</td><td>6.5</td><td>65.2</td><td>20.2</td><td>8.1</td></tr>
  <tr><td>SHA3</td><td>41.89</td><td><b>25.6</b></td><td>0.30x</td><td>4.9</td><td>72.8</td><td>16.1</td><td>6.2</td></tr>
  <tr><td>KMAC</td><td>66.61</td><td><b>16.1</b></td><td>0.19x</td><td>3.0</td><td><b>82.5</b></td><td>10.7</td><td>3.8</td></tr>
</table>

Tweak/key evolution cost per sector on the drive:

| Scheme | µs / sector |
|---|---|
| XTS | 5.4 |
| Ratchet-AES | 7.8–8.0 |
| XEX-SipHash | 20.7 |
| Ratchet-BLAKE3 | 28.5 |
| XEX-BLAKE3 | 28.9 |
| XEX-BLAKE2b | 80.5 |
| XEX-SHA3 | 116.3 |
| XEX-KMAC | 209.6 |

- Every run holds a steady rate (`schemes_throughput.png`), and no scheme degrades over the 1 GiB.
- As the cipher gets cheaper, disk I/O takes a larger share of the time: about 11% for KMAC, 36% for Ratchet-AES, and 63% for ECB. ECB is mostly I/O-bound.
- The XEX schemes spend little time on data (3–13%). The tweak hash decides their speed, ranked SipHash > BLAKE3 > BLAKE2b > SHA3 > KMAC.
- Ratchet-BLAKE3 and XEX-BLAKE3 spend the same evolution time (about 28.5 µs per sector). XEX-BLAKE3 is still faster overall (58 vs 46 MB/s) because its data path is cheaper.

`drive_throughput.csv` is a shorter 100 MB ratcheted run: 40.8 MB/s average, with disk I/O at 56% of wall time.

### 6. Long-run ratcheted AES-XTS drive test (`throughput_plot.png`, about 128 GB)

- **0–3% of the device:** about 63 MB/s, with I/O at about 33% of wall time.
- **3–65%:** about 49 MB/s, with regular dips to about 38 MB/s. I/O rises to about 50%, with spikes at the dips.
- **65–100%:** a step down to about 37 MB/s, with I/O at about 60%. After about 90%, frequent drops to about 8–10 MB/s appear, with I/O spikes up to about 90%.
- The cumulative average ends at about **42 MB/s**.
- Every step and dip comes with a rise in the I/O share, so the slowdown looks like it comes from the drive and not the cipher. Likely causes are SSD write-cache exhaustion or thermal throttling, but this is an inference I have not verified.
