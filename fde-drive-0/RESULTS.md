# FDE Benchmark Results Summary

**Setup:** 128 GB device, 4 KB sectors (31.26M sectors), `O_DIRECT` with 1 MB batched I/O, per-sector crypto.
**Machine:** AMD Ryzen 7 8845HS (8C/16T, 16 MiB L3), Linux 6.14, GCC 13.3, OpenSSL 3.0.13. Benchmark profile `full`, sector size 4096 B.

## Key takeaways

1. **The ratchet costs roughly 30% of drive throughput with AES and about 45% with BLAKE3,** compared with AES-XTS: 61 / 46 MB/s vs 86 MB/s when encrypting a 1 GiB drive.
2. **The ratchet or tweak primitive sets the cost.** One AES-256 ratchet update takes 16.1 ns and one BLAKE3 update takes 95.5 ns (about 6x slower). The XEX tweak hashes range from 65 ns (SipHash) to 836 ns (KMAC). The random-access and per-block evolution costs match these per-update costs closely.
3. **CTR and CBC ratchet modes perform the same.** The two modes are within about 1–5% of each other in every test, so the choice of primitive matters and the choice of mode does not.
4. **Decryption costs the same as encryption.** The exceptions are ECB decrypt (about 14–21% slower) and CBC decrypt in the component breakdown (about 2–4% slower).
5. **Among the XEX tweak hashes, SipHash is the fastest** and slightly beats Ratchet-AES, both on the drive (65 vs 61 MB/s) and in memory (180 vs 154–162 MiB/s). KMAC is the slowest (16 MB/s on the drive, 18 MiB/s in memory).
6. **Random access within a sector costs O(block index) for the ratchets and O(1) for XEX.** Reaching block 256 takes about 4.3 µs with Ratchet-AES and about 25 µs with Ratchet-BLAKE3. XEX takes a constant 105 ns (SipHash) to 870 ns (KMAC) at any block. ECB stays flat at about 31 ns.
7. **Most schemes parallelize well across sectors,** reaching 4.7–6.7x at 8 threads, which is better than OpenSSL XTS (3.25x, limited by memory bandwidth). XEX-SHA3 is the exception: it reaches only 1.66x and is slower at 8 threads than at 4.
8. **In memory, the ratchet is far slower than XTS, but on a real drive I/O hides most of the gap.** Ratchet-AES is about 24x slower than OpenSSL XTS and about 4.8x slower than manual XTS in memory, but only about 1.4x slower than XTS on the drive.

## 1. Ratchet primitive cost (`ratchet_primitives.csv`, 1,000,000 iterations each)

| Primitive | ns / update | TSC cycles / update | vs AES ratchet |
|---|---|---|---|
| XTS tweak doubling, T · α in GF(2^128) | 9.1 | 34.6 | 0.57x |
| Ratchet AES-256(K_G, K ⊕ C) | 16.1 | 61.0 | 1.00x |
| XEX SipHash-2-4-128 | 65.4 | 248.1 | 4.1x |
| XEX keyed BLAKE3 | 95.4 | 361.7 | 5.9x |
| Ratchet BLAKE3(K ‖ C) | 95.5 | 362.4 | 5.9x |
| XEX BLAKE2b-MAC | 288.8 | 1,095.2 | 18.0x |
| XEX SHA3-256 (unkeyed) | 438.6 | 1,663.6 | 27.3x |
| XEX KMAC128 | 836.4 | 3,172.3 | 52.0x |

The XEX hashes all take S ‖ I ‖ C (48 bytes) and output a 16-byte tweak.

- The cheapest and most expensive updates differ by about 90x.
- AES-NI makes the AES ratchet cost only about 1.8x an XTS doubling, even though it is a full block-cipher call.
- Keyed BLAKE3 costs the same as the BLAKE3 ratchet. Both hash 48 bytes in one compression, so the key costs nothing extra.
- SipHash is the cheapest hash, about 1.5x faster than BLAKE3.
- BLAKE2b-MAC, SHA3-256 and KMAC128 are 3–9x more expensive than BLAKE3. KMAC costs about 1.9x SHA3, which fits its extra Keccak permutations for the key and customization string.

## 2. Per-sector component breakdown (`component_breakdown.csv`, 500 iterations)

<table>
  <tr><th>Implementation</th><th>Op</th><th>µs / sector</th><th>Data %</th><th>Evolution %</th><th>Seed %</th><th>Evolution ns / block</th></tr>
  <tr><td rowspan="2">AES-ECB</td><td>enc</td><td>12.3</td><td>100.0</td><td>0.0</td><td>0.00</td><td>0</td></tr>
  <tr><td>dec</td><td>14.0</td><td>100.0</td><td>0.0</td><td>0.00</td><td>0</td></tr>
  <tr><td rowspan="2">AES-XTS-manual</td><td>enc</td><td>21.8</td><td>61.4</td><td>38.3</td><td>0.29</td><td>18.6</td></tr>
  <tr><td>dec</td><td>21.9</td><td>61.7</td><td>38.0</td><td>0.29</td><td>18.6</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-AES</td><td>enc</td><td>41.9</td><td>76.6</td><td>23.3</td><td>0.12</td><td>29.6</td></tr>
  <tr><td>dec</td><td>41.0</td><td>76.5</td><td>23.4</td><td>0.12</td><td>29.0</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-AES</td><td>enc</td><td>42.5</td><td>76.5</td><td>23.4</td><td>0.12</td><td>30.2</td></tr>
  <tr><td>dec</td><td>43.3</td><td>77.2</td><td>22.7</td><td>0.11</td><td>29.9</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-BLAKE3</td><td>enc</td><td>61.4</td><td>48.7</td><td>51.2</td><td>0.07</td><td>104.3</td></tr>
  <tr><td>dec</td><td>61.5</td><td>48.7</td><td>51.3</td><td>0.07</td><td>104.6</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-BLAKE3</td><td>enc</td><td>62.1</td><td>48.3</td><td>51.7</td><td>0.07</td><td>106.4</td></tr>
  <tr><td>dec</td><td>64.5</td><td>49.3</td><td>50.6</td><td>0.07</td><td>108.7</td></tr>
  <tr><td rowspan="2">XEX-SipHash</td><td>enc</td><td>37.4</td><td>27.0</td><td>73.0</td><td>0.00</td><td>79.6</td></tr>
  <tr><td>dec</td><td>37.6</td><td>27.7</td><td>72.3</td><td>0.00</td><td>79.4</td></tr>
  <tr><td rowspan="2">XEX-BLAKE3</td><td>enc</td><td>45.6</td><td>21.6</td><td>78.4</td><td>0.00</td><td>110.6</td></tr>
  <tr><td>dec</td><td>45.5</td><td>21.6</td><td>78.4</td><td>0.00</td><td>110.4</td></tr>
  <tr><td rowspan="2">XEX-BLAKE2b</td><td>enc</td><td>96.5</td><td>8.8</td><td>91.2</td><td>0.00</td><td>309.9</td></tr>
  <tr><td>dec</td><td>95.4</td><td>9.1</td><td>90.9</td><td>0.00</td><td>304.6</td></tr>
  <tr><td rowspan="2">XEX-SHA3</td><td>enc</td><td>134.0</td><td>6.2</td><td>93.8</td><td>0.00</td><td>455.3</td></tr>
  <tr><td>dec</td><td>133.8</td><td>6.5</td><td>93.5</td><td>0.00</td><td>453.8</td></tr>
  <tr><td rowspan="2">XEX-KMAC</td><td>enc</td><td>234.3</td><td>3.5</td><td><b>96.5</b></td><td>0.00</td><td>846.8</td></tr>
  <tr><td>dec</td><td>234.1</td><td>3.5</td><td><b>96.5</b></td><td>0.00</td><td>845.8</td></tr>
  <tr><td>AES-XTS-literal-indexed</td><td>enc</td><td>191.3</td><td>4.2</td><td><b>95.8</b></td><td>0.02</td><td>680.8</td></tr>
</table>

"Evolution ns / block" is the measured evolution time divided by 500 iterations × 256 blocks.

- Seed derivation is negligible (under 0.3%). The XEX schemes report no seed time.
- In the AES ratchets, the data path dominates (about 76%). In the BLAKE3 ratchets, key evolution takes about half of the time.
- In the XEX schemes, the tweak hash takes 72–97% of the time.
- **The XEX data path costs about 7.7 µs per sector, the same as ECB and XTS.** It uses a fixed AES key, while the ratchets spend about 25 µs per sector on data. That is why XEX-BLAKE3 beats Ratchet-BLAKE3 (45.6 vs 61.4 µs) even though both spend about 105–110 ns per block on evolution.
- In "literal-indexed" XTS, which recomputes the tweak from the index for every block, 96% of the time goes to tweak evolution. It is 8.8x slower than incremental XTS. This file has an encrypt row only for this implementation.
- Decryption costs the same as encryption, except ECB decrypt (about 14% slower) and CBC decrypt (about 2–4% slower).

## 3. Random access within a sector (`random_access.csv`, latency to reach block *k*)

Mean latency in ns (warm cache, 1,000 samples):

| Scheme | k=1 | k=32 | k=64 | k=128 | k=256 | ≈ ns / block |
|---|---|---|---|---|---|---|
| AES-ECB | 31 | 31 | 31 | 31 | 31 | 0 (O(1)) |
| AES-XTS-manual | 55 | 189 | 369 | 663 | 1,295 | ~4.9 |
| Ratchet-CTR-AES | 121 | 638 | 1,173 | 2,231 | 4,388 | ~16.7 |
| Ratchet-CBC-AES | 123 | 648 | 1,151 | 2,183 | 4,286 | ~16.3 |
| Ratchet-CTR-BLAKE3 | 124 | 3,133 | 6,304 | 12,376 | 24,683 | ~96.3 |
| Ratchet-CBC-BLAKE3 | 133 | 3,199 | 6,431 | 12,694 | 25,176 | ~98.2 |
| XEX-SipHash | 111 | 105 | 106 | 105 | 105 | 0 (O(1)) |
| XEX-BLAKE3 | 135 | 136 | 135 | 136 | 142 | 0 (O(1)) |
| XEX-BLAKE2b | 333 | 326 | 324 | 327 | 319 | 0 (O(1)) |
| XEX-SHA3 | 567 | 547 | 548 | 557 | 548 | 0 (O(1)) |
| XEX-KMAC | 876 | 892 | 869 | 867 | 863 | 0 (O(1)) |

- For the ratchets and XTS, latency grows linearly with *k*. The per-block slope matches the primitive costs in Section 1 (16.1 ns for AES, 95.5 ns for BLAKE3).
- **XEX random access is constant time.** The tweak for block *j* depends only on S, I_j and C_{j-1}, and C_{j-1} is already stored, so one hash plus one AES call reaches any block. The constant is one hash update plus about 35–40 ns (about 110 ns for SHA3).
- At block 256, XEX-SipHash is about 40x faster than Ratchet-AES and XEX-BLAKE3 is about 175x faster than Ratchet-BLAKE3. XEX loses only for the first few blocks; for example, XEX-KMAC is slower than Ratchet-AES up to about *k* ≈ 50.
- **Cache-thrashed** runs (80 samples) add a roughly constant **200–350 ns** to the ratchets, mostly visible at small *k*, and have higher variance. The slope is unchanged. The XEX schemes roughly double, for example SHA3 at 1.1–1.2 µs and KMAC at 1.5–1.7 µs, probably because the OpenSSL hash contexts fall out of cache.

## 4. Parallel scaling (`parallel_scaling.csv`, 64 MiB volume, 3 trials)

| Implementation | 1 thread (MiB/s) | 8 threads (MiB/s) | Speedup @8 | Efficiency @8 |
|---|---|---|---|---|
| AES-ECB | 1,047 | 6,884 | 6.57x | 0.82 |
| AES-XTS-manual | 736 | 3,800 | 5.17x | 0.65 |
| AES-XTS-OpenSSL (full sector) | 3,859 | 12,525 | 3.25x | 0.41 |
| Ratchet-CTR-AES | 143 | 700 | 4.88x | 0.61 |
| Ratchet-CBC-AES | 161 | 755 | 4.70x | 0.59 |
| Ratchet-CTR-BLAKE3 | 84.3 | 427 | 5.07x | 0.63 |
| Ratchet-CBC-BLAKE3 | 86.9 | 470 | 5.41x | 0.68 |
| XEX-SipHash | 175 | **938** | 5.37x | 0.67 |
| XEX-BLAKE3 | 130 | 875 | **6.73x** | **0.84** |
| XEX-BLAKE2b | 50.8 | 288 | 5.67x | 0.71 |
| XEX-SHA3 | 33.2 | 55.2 | **1.66x** | **0.21** |
| XEX-KMAC | 18.5 | 105 | 5.68x | 0.71 |

- Up to 4 threads, most schemes scale almost linearly (efficiency of at least 0.81). The exceptions are OpenSSL XTS (0.64), XEX-SHA3 (0.54), and Ratchet-CTR-AES at 2 threads (0.68).
- OpenSSL XTS is memory-bound at 8 threads. The ratchets and most XEX schemes are compute-bound, so they keep scaling.
- **XEX-SipHash and XEX-BLAKE3 are the fastest ratcheted schemes at 8 threads** (938 and 875 MiB/s), ahead of both AES ratchets.
- **XEX-SHA3 stops scaling.** It peaks at 71.8 MiB/s with 4 threads and drops to 55.2 MiB/s with 8. A likely cause, which I have not verified: `uh_sha3_256` passes `EVP_sha3_256()` to `EVP_DigestInit_ex` on every call. In OpenSSL 3 that triggers an implicit algorithm fetch, which takes a global lock. The MAC-based schemes fetch their algorithm once per worker (`EVP_MAC_fetch`) and scale normally.
- Single-threaded, Ratchet-AES is about 27x slower than OpenSSL XTS and about 5x slower than manual XTS.
- Ratchet-CTR-AES at 2 threads (1.36x) is out of line with its 4-thread result (3.26x). This is probably noise from only 3 trials.

## 5. In-memory throughput and latency (`throughput.csv`, 32 MiB volume, 5 trials)

Mean results for 4096 B sectors:

<table>
  <tr><th>Implementation</th><th>Op</th><th>MiB/s</th><th>µs / sector</th><th>TSC cycles / byte</th><th>vs XTS-manual</th></tr>
  <tr><td rowspan="2">AES-ECB</td><td>enc</td><td>1,190.5</td><td>3.3</td><td>3.04</td><td>1.58x</td></tr>
  <tr><td>dec</td><td>940.1</td><td>4.2</td><td>3.85</td><td>1.37x</td></tr>
  <tr><td rowspan="2">AES-XTS-manual</td><td>enc</td><td>751.7</td><td>5.2</td><td>4.81</td><td>1.00x</td></tr>
  <tr><td>dec</td><td>688.2</td><td>5.7</td><td>5.26</td><td>1.00x</td></tr>
  <tr><td rowspan="2">AES-XTS-OpenSSL (full sector)</td><td>enc</td><td><b>3,739.4</b></td><td>1.0</td><td>0.97</td><td>4.97x</td></tr>
  <tr><td>dec</td><td><b>4,006.8</b></td><td>1.0</td><td>0.90</td><td>5.82x</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-AES</td><td>enc</td><td>154.2</td><td>25.3</td><td>23.45</td><td>0.21x</td></tr>
  <tr><td>dec</td><td>157.6</td><td>24.8</td><td>22.95</td><td>0.23x</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-AES</td><td>enc</td><td>161.5</td><td>24.2</td><td>22.40</td><td>0.21x</td></tr>
  <tr><td>dec</td><td>156.4</td><td>25.0</td><td>23.13</td><td>0.23x</td></tr>
  <tr><td rowspan="2">Ratchet-CTR-BLAKE3</td><td>enc</td><td>85.1</td><td>45.9</td><td>42.49</td><td>0.11x</td></tr>
  <tr><td>dec</td><td>82.8</td><td>47.2</td><td>43.71</td><td>0.12x</td></tr>
  <tr><td rowspan="2">Ratchet-CBC-BLAKE3</td><td>enc</td><td>86.8</td><td>45.0</td><td>41.68</td><td>0.12x</td></tr>
  <tr><td>dec</td><td>84.9</td><td>46.0</td><td>42.61</td><td>0.12x</td></tr>
  <tr><td rowspan="2">XEX-SipHash</td><td>enc</td><td><b>179.5</b></td><td>21.8</td><td>20.15</td><td>0.24x</td></tr>
  <tr><td>dec</td><td><b>181.3</b></td><td>21.5</td><td>19.95</td><td>0.26x</td></tr>
  <tr><td rowspan="2">XEX-BLAKE3</td><td>enc</td><td>131.1</td><td>29.8</td><td>27.60</td><td>0.17x</td></tr>
  <tr><td>dec</td><td>134.6</td><td>29.0</td><td>26.88</td><td>0.20x</td></tr>
  <tr><td rowspan="2">XEX-BLAKE2b</td><td>enc</td><td>49.8</td><td>78.4</td><td>72.59</td><td>0.07x</td></tr>
  <tr><td>dec</td><td>50.4</td><td>77.5</td><td>71.73</td><td>0.07x</td></tr>
  <tr><td rowspan="2">XEX-SHA3</td><td>enc</td><td>34.1</td><td>114.6</td><td>106.15</td><td>0.05x</td></tr>
  <tr><td>dec</td><td>33.0</td><td>118.5</td><td>109.69</td><td>0.05x</td></tr>
  <tr><td rowspan="2">XEX-KMAC</td><td>enc</td><td>18.0</td><td>217.4</td><td>201.35</td><td>0.02x</td></tr>
  <tr><td>dec</td><td>17.9</td><td>218.0</td><td>201.89</td><td>0.03x</td></tr>
</table>

- The ranking matches Sections 2 and 5: OpenSSL XTS > ECB > manual XTS > XEX-SipHash > Ratchet-AES > XEX-BLAKE3 > Ratchet-BLAKE3 > XEX-BLAKE2b > XEX-SHA3 > XEX-KMAC.
- Ratchet-AES runs at about 0.21x manual XTS and about 0.04x OpenSSL XTS.
- Decryption runs at the same speed as encryption for every ratcheted and XEX scheme, within about 3%. ECB decrypt is about 21% slower, and manual XTS decrypt is about 8% slower.
- **Sector size and volume size barely matter for the ratcheted schemes.** At 512 B sectors and with a 1 MiB volume, they stay within about 5% of the 4096 B / 32 MiB numbers. That is expected when the cost is per block.
- **OpenSSL XTS depends strongly on sector size:** 1,093 MiB/s at 512 B vs 3,739 MiB/s at 4096 B. Per-call setup dominates small sectors.
- **In memory vs on the drive:** XEX-SipHash goes from 180 MiB/s in memory to 65 MB/s on the drive, and Ratchet-AES from about 158 MiB/s to 61 MB/s. The drive and its I/O path take most of the wall time.
- For ECB and OpenSSL XTS, the mean and median differ by up to 15% (for example ECB enc: mean 1,190, median 1,327 MiB/s), so the fast schemes are noisy over 5 trials.

## 6. Full-drive encryption, 1 GiB (`drive_encrypt_*.csv`, 262,144 sectors, encrypt only)

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

| Scheme | µs / sector | ns / block (÷ 256) | Microbenchmark (ns / update, Section 1) |
|---|---|---|---|
| XTS | 5.4 | 21.2 | 9.1 |
| Ratchet-AES | 7.8–8.0 | 30.5–31.2 | 16.1 |
| XEX-SipHash | 20.7 | 80.9 | 65.4 |
| Ratchet-BLAKE3 | 28.5 | 111.5 | 95.5 |
| XEX-BLAKE3 | 28.9 | 112.8 | 95.4 |
| XEX-BLAKE2b | 80.5 | 314.5 | 288.8 |
| XEX-SHA3 | 116.3 | 454.3 | 438.6 |
| XEX-KMAC | 209.6 | 818.7 | 836.4 |

- Every run holds a steady rate (`schemes_throughput.png`), and no scheme degrades over the 1 GiB.
- As the cipher gets cheaper, disk I/O takes a larger share of the time: about 11% for KMAC, 36% for Ratchet-AES, and 63% for ECB. ECB is mostly I/O-bound.
- The XEX schemes spend little time on data (3–13%). The tweak hash decides their speed, ranked SipHash > BLAKE3 > BLAKE2b > SHA3 > KMAC.
- Ratchet-BLAKE3 and XEX-BLAKE3 spend the same evolution time (about 28.5 µs per sector). XEX-BLAKE3 is still faster overall (58 vs 46 MB/s) because its data path is cheaper (Section 2).
- The drive's per-block evolution cost matches the microbenchmark ranking exactly and is about 12–26 ns higher per block. The extra is most likely the per-block `now_ns()` timing in the drive loop. KMAC is the one scheme slightly below its microbenchmark figure.

`drive_throughput.csv` is a shorter 100 MB ratcheted run: 40.8 MB/s average, with disk I/O at 56% of wall time.

## 7. Long-run ratcheted AES-XTS drive test (`throughput_plot.png`, about 128 GB)

- **0–3% of the device:** about 63 MB/s, with I/O at about 33% of wall time.
- **3–65%:** about 49 MB/s, with regular dips to about 38 MB/s. I/O rises to about 50%, with spikes at the dips.
- **65–100%:** a step down to about 37 MB/s, with I/O at about 60%. After about 90%, frequent drops to about 8–10 MB/s appear, with I/O spikes up to about 90%.
- The cumulative average ends at about **42 MB/s**.
- Every step and dip comes with a rise in the I/O share, so the slowdown looks like it comes from the drive and not the cipher. Likely causes are SSD write-cache exhaustion or thermal throttling, but this is an inference I have not verified.

## Caveats / data issues

- The drive tests cover **encryption only**, so on-drive decryption is not measured.
- The drive CSVs and both figures are identical to the previous upload. Only the in-memory benchmark files (Sections 1–5) are new.
- The plotted 128 GB run has no matching CSV in `results.zip`, so I read its numbers off the figure and they are approximate.
- The drive CSV header has shifted names (`data_n,sevolution_ns` instead of `data_ns,evolution_ns`).
- In `schemes_throughput.png`, the title still says "Ratcheted AES-XTS", cbc-aes and xts share the same colour, and the I/O legend covers the plot.
- `run_metadata.txt` is dated 2026-11-19, but `environment.txt` was captured on 2026-10-03, so the environment file is from an earlier run.
- **The TSC column is not real core cycles.** Cycles ÷ ns is exactly 3.79 on every row, because the TSC ticks at a fixed rate regardless of boost clocks. Treat it as reference cycles.
- The primitive numbers in this run are about 20% lower than an earlier run (for example AES 16.1 vs 20.7 ns). Each row is a single 1M-iteration trial, so report a median of several runs with a pinned CPU and the `performance` governor.
- BLAKE3 is built with SIMD disabled (`-DBLAKE3_NO_SSE2/SSE41/AVX2/AVX512`), so all BLAKE3 numbers are for the portable C version.
- SipHash, BLAKE2b-MAC and KMAC call `EVP_MAC_init` with the key on every update, so part of their cost is OpenSSL setup rather than the hash itself.
- The parallel scaling test stops at 8 threads, although the machine has 16 logical CPUs. Each point uses only 3 trials.
