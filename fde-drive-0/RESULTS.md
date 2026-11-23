# XEX mask-candidate measurements

Measured on the reference machine: AMD Ryzen 7 8845HS (8C/16T, 16 MiB L3), Linux 6.14, GCC 13.3, OpenSSL 3.0.13, repository build flags, benchmark profile `full`, 4096 B sectors. Run of 2026-11-22. Numbers from other machines are not comparable.

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

## 1. ns per mask update (component-breakdown method)

Source: `component_breakdown.csv`, 500 iterations of one 4096 B sector (256 blocks). "ns / mask update" is the measured evolution time ÷ (500 × 256). The microbenchmark column is the 1M-iteration chained loop in `ratchet_primitives.csv`, which does not yet include BLAKE2s, HMAC-SHA256, CMAC or GHASH.

<table>
  <tr><th>Scheme</th><th>Mask</th><th>Op</th><th>ns / mask update</th><th>µs / sector</th><th>Evolution %</th><th>Microbenchmark ns / update</th></tr>
  <tr><td rowspan="2">XEX-SipHash</td><td rowspan="2">keyed</td><td>enc</td><td><b>75.5</b></td><td>35.8</td><td>72.4</td><td rowspan="2">63.3</td></tr>
  <tr><td>dec</td><td><b>76.7</b></td><td>36.5</td><td>72.2</td></tr>
  <tr><td rowspan="2">XEX-BLAKE3</td><td rowspan="2">keyed</td><td>enc</td><td><b>103.8</b></td><td>42.9</td><td>78.7</td><td rowspan="2">97.5</td></tr>
  <tr><td>dec</td><td><b>103.2</b></td><td>42.8</td><td>78.1</td></tr>
  <tr><td rowspan="2">XEX-BLAKE2s</td><td rowspan="2">keyed</td><td>enc</td><td><b>254.2</b></td><td>81.9</td><td>89.7</td><td rowspan="2">–</td></tr>
  <tr><td>dec</td><td><b>252.2</b></td><td>81.4</td><td>89.5</td></tr>
  <tr><td rowspan="2">XEX-BLAKE2b</td><td rowspan="2">keyed</td><td>enc</td><td><b>304.1</b></td><td>94.6</td><td>91.3</td><td rowspan="2">291.8</td></tr>
  <tr><td>dec</td><td><b>303.0</b></td><td>94.4</td><td>91.1</td></tr>
  <tr><td rowspan="2">XEX-SHA3</td><td rowspan="2">unkeyed (negative control)</td><td>enc</td><td><b>449.9</b></td><td>132.7</td><td>93.6</td><td rowspan="2">426.8</td></tr>
  <tr><td>dec</td><td><b>434.8</b></td><td>128.6</td><td>93.5</td></tr>
  <tr><td rowspan="2">XEX-HMAC-SHA256</td><td rowspan="2">keyed</td><td>enc</td><td><b>473.2</b></td><td>137.9</td><td>94.2</td><td rowspan="2">–</td></tr>
  <tr><td>dec</td><td><b>483.8</b></td><td>140.7</td><td>94.3</td></tr>
  <tr><td rowspan="2">XEX-CMAC</td><td rowspan="2">keyed</td><td>enc</td><td><b>538.6</b></td><td>154.7</td><td>94.9</td><td rowspan="2">–</td></tr>
  <tr><td>dec</td><td><b>550.9</b></td><td>158.0</td><td>94.9</td></tr>
  <tr><td rowspan="2">XEX-KMAC</td><td rowspan="2">keyed</td><td>enc</td><td><b>801.4</b></td><td>222.1</td><td>96.4</td><td rowspan="2">794.5</td></tr>
  <tr><td>dec</td><td><b>802.8</b></td><td>222.6</td><td>96.4</td></tr>
  <tr><td rowspan="2">XEX-GHASH</td><td rowspan="2">keyed</td><td>enc</td><td><b>4,283.8</b></td><td>1,113.5</td><td>99.3</td><td rowspan="2">–</td></tr>
  <tr><td>dec</td><td><b>4,279.8</b></td><td>1,112.6</td><td>99.3</td></tr>
</table>

Reference rows (not XEX candidates):

<table>
  <tr><th>Scheme</th><th>Mask</th><th>Op</th><th>ns / mask update</th><th>µs / sector</th><th>Evolution %</th><th>Microbenchmark ns / update</th></tr>
  <tr><td rowspan="2">AES-XTS-manual (T·α)</td><td rowspan="2">reference</td><td>enc</td><td><b>17.8</b></td><td>20.9</td><td>38.4</td><td rowspan="2">8.4</td></tr>
  <tr><td>dec</td><td><b>21.1</b></td><td>25.1</td><td>37.8</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-AES</td><td rowspan="2">reference</td><td>enc</td><td><b>30.9</b></td><td>41.6</td><td>24.6</td><td rowspan="2">15.6</td></tr>
  <tr><td>dec</td><td><b>30.9</b></td><td>41.6</td><td>24.6</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-AES</td><td rowspan="2">reference</td><td>enc</td><td><b>30.2</b></td><td>40.0</td><td>25.1</td><td rowspan="2">15.6</td></tr>
  <tr><td>dec</td><td><b>29.9</b></td><td>41.5</td><td>23.6</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-BLAKE3</td><td rowspan="2">reference</td><td>enc</td><td><b>104.4</b></td><td>61.4</td><td>51.4</td><td rowspan="2">96.1</td></tr>
  <tr><td>dec</td><td><b>103.8</b></td><td>60.8</td><td>51.6</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-BLAKE3</td><td rowspan="2">reference</td><td>enc</td><td><b>101.6</b></td><td>59.4</td><td>51.7</td><td rowspan="2">96.1</td></tr>
  <tr><td>dec</td><td><b>102.3</b></td><td>61.1</td><td>50.4</td></tr>
</table>

`component_breakdown.csv` also has one `AES-XTS-literal-indexed` row (enc only): 642.6 ns per tweak, 180.6 µs per sector. It recomputes the tweak for each block from its index instead of doubling, so it is not comparable with the rows above.

- **Ranking of the keyed candidates:** SipHash (76 ns) < BLAKE3 (104) < BLAKE2s (253) < BLAKE2b (304) < HMAC-SHA256 (478) < CMAC (545) < KMAC (802) < GHASH (4,282). The unkeyed SHA3 control (442 ns) sits between BLAKE2b and HMAC-SHA256.
- **Only SipHash and BLAKE3 cost about the same as the ratchet primitives.** SipHash is about 2.5x a Ratchet-AES update, and keyed BLAKE3 costs the same as the BLAKE3 ratchet. Every other candidate is 2.4–41x more expensive than keyed BLAKE3.
- **The XEX data path is cheap.** Every XEX scheme spends about 7.2–7.8 µs per sector on data, the same as ECB (7.0–7.3 µs), because the AES data key is fixed. The ratchets spend about 25 µs per sector on data. So the mask hash decides XEX speed: it takes 72% (SipHash) to 99% (GHASH) of the sector time.
- **GHASH is by far the slowest (about 4.3 µs per update)** because it is the bitwise reference implementation (SP 800-38D Algorithm 1). A table-driven or PCLMULQDQ GHASH would be much faster; that is an expectation, not a measurement.
- **CMAC and HMAC-SHA256 cost more than their hash work suggests.** CMAC over 48 bytes is only three AES blocks, and HMAC-SHA256 is a few SHA-256 compressions. Both re-run `EVP_MAC_init` with the key on every update, which probably accounts for most of their cost (inference, not profiled).
- **BLAKE2s is about 17% cheaper than BLAKE2b** for this 48-byte input.
- **The BLAKE2b digest-size change did not change its cost.** It is 304 ns per update, against about 307 ns for the previous truncated version (2026-11-19 run).
- Decryption costs the same as encryption, within about 2%.
- The breakdown method is 6–15 ns higher than the microbenchmark (for example SipHash 76 vs 63 ns, BLAKE2b 304 vs 292 ns). That gap is the per-block timer overhead.

## 2. 1 GiB drive throughput (`drive_encrypt_*.csv`, 262,144 sectors, encrypt only)

<table>
  <tr><th>Family</th><th>Scheme</th><th>Time (s)</th><th>Avg MB/s</th><th>vs XTS</th><th>Data %</th><th>Evolution %</th><th>Disk I/O %</th><th>Other %</th><th>Evolution ns / block</th></tr>
  <tr><td rowspan="2">Baseline</td><td>ECB</td><td>9.66</td><td><b>111.2</b></td><td>1.29x</td><td>24.1</td><td>0.0</td><td>60.5</td><td>15.3</td><td>0.0</td></tr>
  <tr><td>XTS</td><td>12.44</td><td><b>86.3</b></td><td>1.00x</td><td>17.6</td><td>11.4</td><td>49.2</td><td>21.7</td><td>21.2</td></tr>
  <tr><td rowspan="2">Ratchet-AES</td><td>CTR</td><td>17.51</td><td><b>61.3</b></td><td>0.71x</td><td>38.3</td><td>11.7</td><td>35.2</td><td>14.7</td><td>30.5</td></tr>
  <tr><td>CBC</td><td>17.47</td><td><b>61.5</b></td><td>0.71x</td><td>38.6</td><td>11.7</td><td>34.9</td><td>14.7</td><td>30.5</td></tr>
  <tr><td rowspan="2">Ratchet-BLAKE3</td><td>CTR</td><td>23.03</td><td><b>46.6</b></td><td>0.54x</td><td>29.9</td><td>32.1</td><td>26.6</td><td>11.3</td><td>110.3</td></tr>
  <tr><td>CBC</td><td>23.19</td><td><b>46.3</b></td><td>0.54x</td><td>29.4</td><td>32.7</td><td>26.6</td><td>11.3</td><td>112.9</td></tr>
  <tr><td rowspan="8">XEX (keyed mask)</td><td>SipHash</td><td>16.30</td><td><b>65.9</b></td><td>0.76x</td><td>12.8</td><td>33.5</td><td>37.7</td><td>16.0</td><td>81.3</td></tr>
  <tr><td>BLAKE3</td><td>18.41</td><td><b>58.3</b></td><td>0.68x</td><td>11.2</td><td>41.3</td><td>33.5</td><td>14.0</td><td>113.4</td></tr>
  <tr><td>BLAKE2s</td><td>29.65</td><td><b>36.2</b></td><td>0.42x</td><td>7.1</td><td>62.8</td><td>21.2</td><td>8.9</td><td>277.3</td></tr>
  <tr><td>BLAKE2b</td><td>33.26</td><td><b>32.3</b></td><td>0.37x</td><td>6.4</td><td>66.5</td><td>19.3</td><td>7.9</td><td>329.5</td></tr>
  <tr><td>HMAC-SHA256</td><td>44.07</td><td><b>24.4</b></td><td>0.28x</td><td>4.6</td><td>74.9</td><td>14.6</td><td>5.9</td><td>491.7</td></tr>
  <tr><td>CMAC</td><td>49.20</td><td><b>21.8</b></td><td>0.25x</td><td>4.4</td><td>77.3</td><td>13.1</td><td>5.2</td><td>566.6</td></tr>
  <tr><td>KMAC</td><td>67.03</td><td><b>16.0</b></td><td>0.19x</td><td>3.0</td><td>83.2</td><td>10.0</td><td>3.8</td><td>830.8</td></tr>
  <tr><td>GHASH</td><td>305.24</td><td><b>3.5</b></td><td>0.04x</td><td>0.6</td><td>96.3</td><td>2.2</td><td>0.8</td><td>4,380.2</td></tr>
  <tr><td rowspan="1">XEX (negative control)</td><td>SHA3 (unkeyed)</td><td>41.65</td><td><b>25.8</b></td><td>0.30x</td><td>5.0</td><td>73.3</td><td>15.5</td><td>6.2</td><td>454.9</td></tr>
</table>

"vs XTS" is relative to 86.3 MB/s. "Evolution ns / block" is the on-drive evolution time ÷ (262,144 × 256).

- **XEX-SipHash is the fastest ratcheted scheme on the drive** (65.9 MB/s, 0.76x XTS), ahead of Ratchet-AES (61.3–61.5 MB/s). XEX-BLAKE3 (58.3 MB/s) is close behind and well ahead of Ratchet-BLAKE3 (46.3–46.6 MB/s).
- **Every other keyed candidate is slower than Ratchet-BLAKE3:** BLAKE2s 36.2, BLAKE2b 32.3, HMAC-SHA256 24.4, CMAC 21.8, KMAC 16.0 and GHASH 3.5 MB/s. HMAC-SHA256 and CMAC are even slower than the unkeyed SHA3 control (25.8 MB/s).
- Disk I/O takes a smaller share as the mask gets more expensive: 38% for SipHash, 10% for KMAC and 2% for GHASH. Only the cheap candidates are close to I/O-bound.
- On-drive evolution per block matches the breakdown method within about 5–30 ns for every scheme (about 100 ns, or 2%, for GHASH) (for example CMAC 567 vs 545 ns, GHASH 4,380 vs 4,282 ns). The order is identical.
- Every run holds a steady rate across the 1 GiB (`schemes_throughput.png`).
- Ratchet-AES, Ratchet-BLAKE3, ECB and XTS are within 1–7% of the 2026-11-19 run.

## 3. Parallel scaling (`parallel_scaling.csv`, 64 MiB volume, 4096 B sectors, 3 trials, MiB/s)

| Implementation | 1 thread | 2 threads | 4 threads | 8 threads | Speedup @8 | Efficiency @8 |
|---|---|---|---|---|---|---|
| AES-ECB | 1,024 | 2,302 | 3,798 | 4,361 | 4.26x | 0.53 |
| AES-XTS-manual | 769 | 1,435 | 2,748 | 3,513 | 4.57x | 0.57 |
| AES-XTS-OpenSSL (full sector) | 3,051 | 3,843 | 4,207 | 4,344 | **1.42x** | **0.18** |
| Ratchet-CTR-AES | 155 | 296 | 510 | 846 | 5.46x | 0.68 |
| Ratchet-CBC-AES | 167 | 322 | 583 | 846 | 5.08x | 0.63 |
| Ratchet-CTR-BLAKE3 | 87.1 | 168 | 325 | 497 | 5.71x | 0.71 |
| Ratchet-CBC-BLAKE3 | 91.5 | 177 | 346 | 528 | 5.78x | 0.72 |
| XEX-SipHash | 184 | 350 | 624 | 1,006 | 5.48x | 0.68 |
| XEX-BLAKE3 | 135 | 261 | 504 | 845 | 6.24x | 0.78 |
| XEX-BLAKE2s | 58.7 | 115 | 220 | 360 | 6.13x | 0.77 |
| XEX-BLAKE2b | 48.6 | 93.3 | 181 | 293 | 6.03x | 0.75 |
| XEX-SHA3 (negative control) | 34.4 | 57.5 | 75.7 | 56.9 | **1.65x** | **0.21** |
| XEX-HMAC-SHA256 | 31.6 | 46.5 | 63.0 | 56.9 | **1.80x** | **0.22** |
| XEX-CMAC | 27.9 | 45.3 | 61.0 | 55.9 | **2.01x** | **0.25** |
| XEX-KMAC | 18.7 | 36.2 | 66.9 | 110 | 5.85x | 0.73 |
| XEX-GHASH | 3.5 | 6.8 | 13.0 | 21.4 | 6.04x | 0.75 |

- **Most XEX candidates scale well,** at 5.5–6.2x on 8 threads (efficiency 0.68–0.78). XEX-SipHash reaches 1,006 MiB/s at 8 threads, the highest of any ratcheted scheme.
- **XEX-SHA3, XEX-HMAC-SHA256 and XEX-CMAC stop scaling.** They reach only 1.65–2.0x at 8 threads and run slower at 8 threads than at 4. All three go through an OpenSSL digest or cipher that is named on every call: `EVP_sha3_256()` for SHA3, and probably the underlying digest/cipher parameters on each `EVP_MAC_init` for HMAC and CMAC. In OpenSSL 3 that does an implicit algorithm fetch under a global lock. This is a likely cause, not verified. SipHash, BLAKE2s/b and KMAC have no inner algorithm and scale normally.
- **OpenSSL XTS only reached 1.42x (4,345 MiB/s at 8 threads) in this run,** compared with 3.25x (12,525 MiB/s) on 2026-11-19. Its single-thread rate also fell from 3,859 to 3,051 MiB/s. ECB (4.26x vs 6.57x) and manual XTS also scaled worse. Treat the baseline 8-thread rows as unreliable for this run and rerun them, ideally with more than 3 trials.
- At 8 threads the ratchets reach 5.1–5.8x, about the same as before.

## Caveats

- Each in-memory row is a single run (500 iterations, 1M iterations, or 3 trials). For final numbers, report the median of several runs with the CPU pinned and the `performance` governor.
- **The TSC is not real core cycles.** Cycles ÷ ns is fixed at about 3.78, so treat TSC values as reference cycles.
- BLAKE3 is built with SIMD disabled (`-DBLAKE3_NO_SSE2/SSE41/AVX2/AVX512`), so all BLAKE3 numbers are for the portable C version.
- The keyed MAC candidates call `EVP_MAC_init` with the key on every update, so OpenSSL setup is included in their cost.
- `drive_throughput.csv` and `throughput_plot.png` are unchanged from earlier uploads (dated 2026-11-17).
- In `schemes_throughput.png`, 15 schemes share the 10-colour palette, so colours repeat (for example cbc-aes, xex-hmac-sha256 and xts are all blue), and both legends cover the plots.
- The drive CSV header still has shifted names (`data_n,sevolution_ns`).

## Summary
| Mask hash | ns / update | 1 GiB drive MB/s (vs XTS) | 8-thread speedup | AXU |
|---|---|---|---|---|
| BLAKE2s | 253 | 36.2 (0.42x) | 6.13x | Assumed |
| HMAC-SHA256 | 478 | 24.4 (0.28x) | 1.80x | Assumed |
| CMAC | 545 | 21.8 (0.25x) | 2.01x | Assumed |
| KMAC128 | 802 | 16.0 (0.19x) | 5.85x | Assumed |
| GHASH (bitwise reference) | 4,282 | 3.5 (0.04x) | 6.04x | Proven, ε ≤ 3/2^128 |

**Conclusion.** We choose BLAKE2s because it is the fastest of the five candidates:

- 1.9x faster per mask update than the next candidate, HMAC-SHA256;
- the highest drive throughput (36.2 MB/s);
- near-linear scaling to 8 threads (6.1x), whereas HMAC-SHA256 and CMAC stop at about 2x.

It also takes a key and outputs a 16-byte mask natively, so no truncation or wrapper construction is needed. GHASH has a proven AXU bound, but our reference implementation is about 17x slower than BLAKE2s, so it is not competitive as implemented.
