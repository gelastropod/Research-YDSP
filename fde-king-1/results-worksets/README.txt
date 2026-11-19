FDE King 1 run summary
Requested fresh-process sessions: 6
CPU: 13th Gen Intel(R) Core(TM) i7-1365U; logical CPUs: 12; affinity: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
OS: Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.43; Python: 3.14.4; GIL: True
Backend: OpenSSL 4.0.1 9 Jun 2026; AES-NI available: True; CLMUL available: True
RQ1-3 calling threads: 1; RQ4 worker counts: [1, 2, 4]; thread batches KiB: [256]
Working sets MiB: [1.0, 4.0]; sector sizes: [512, 4096]; throughput trials/condition/launch: 5
RQs: [2]; schemes: ecb_bulk, xts_library, xts_manual_ni, xex_blake2s, cbc_mac, lrw_horner, lrw_precompute
Point estimates: median of per-launch medians. Multi-launch error bars: conservative pointwise >=95% order-statistic CIs.
Six or more launches: binomial order-statistic intervals (paired launch ratios for comparisons); requires independent, comparable launches.
Single launch: circular adjacent-pair bootstrap of batches; these CIs exclude between-launch variation.
Two to five launches: finite distribution-free two-sided 95% median intervals are unavailable; error bars are omitted. Six launches give at least 96.875% coverage under the stated assumptions.
The number of profiling rows or hash calls is not the number of independent machine launches.
The shaded +/-5% band on ratio plots is a practical tolerance, not an error bar.
Baseline thread speedup is 1 by definition; no CI is claimed for that identity.
LRW precompute and Horner are algebraically identical, use the same key, and are tested for identical ciphertext.
LRW precompute: initial table payload 4096 bytes (256 positions); grows for longer sectors. Setup and payload are reported.
RQ3 prebuilt independent inputs exclude input assembly; feedback includes assembly. CBC is a full three-stage call.
RQ3 LRW precompute full-context call recomputes the sector term; sector encryption/decryption amortizes it once per sector.
RQ1 records one row per instrumented 4096-byte sector; clock calls perturb this path. Throughput is uninstrumented.
Key/context and thread-pool setup excluded from steady-state throughput. OpenSSL per-sector context creation remains included.
RAM only, no disk I/O; CPU only, no GPU/CUDA. No estimated cycle counts.
These measurements do not prove cryptographic security.
Raw per-session CSVs and environment snapshots: [RAW]/. Figures: [FIGURES]/.
Check status.json for completion; summary CSVs state actual session and sample counts even for partial analysis.

Throughput (MiB/s):
1 MiB; 512 B; decrypt; AES-ECB · bulk: 253.034 [246.276, 257.966]
1 MiB; 512 B; decrypt; AES-XTS · OpenSSL whole-sector: 151.411 [144.426, 157.040]
1 MiB; 512 B; decrypt; AES-MAC-CBC: 40.576 [39.044, 41.742]
1 MiB; 512 B; decrypt; AES-XTS · manual, AES-NI requested: 33.008 [32.054, 35.120]
1 MiB; 512 B; decrypt; XEX · keyed BLAKE2s: 24.913 [24.252, 25.553]
1 MiB; 512 B; decrypt; LRW-precompute: 9.165 [8.891, 9.415]
1 MiB; 512 B; decrypt; LRW-Horner: 7.889 [7.648, 8.045]
1 MiB; 512 B; encrypt; AES-ECB · bulk: 251.627 [243.180, 254.336]
1 MiB; 512 B; encrypt; AES-XTS · OpenSSL whole-sector: 142.494 [139.968, 143.950]
1 MiB; 512 B; encrypt; AES-XTS · manual, AES-NI requested: 33.728 [33.107, 34.331]
1 MiB; 512 B; encrypt; XEX · keyed BLAKE2s: 6.734 [6.630, 7.139]
1 MiB; 512 B; encrypt; LRW-precompute: 4.589 [4.512, 4.839]
1 MiB; 512 B; encrypt; AES-MAC-CBC: 4.509 [4.451, 4.744]
1 MiB; 512 B; encrypt; LRW-Horner: 4.080 [4.029, 4.315]
1 MiB; 4096 B; decrypt; AES-ECB · bulk: 1231.268 [1185.347, 1249.856]
1 MiB; 4096 B; decrypt; AES-XTS · OpenSSL whole-sector: 859.900 [742.983, 919.540]
1 MiB; 4096 B; decrypt; AES-MAC-CBC: 263.999 [244.405, 270.161]
1 MiB; 4096 B; decrypt; AES-XTS · manual, AES-NI requested: 56.846 [54.249, 58.399]
1 MiB; 4096 B; decrypt; XEX · keyed BLAKE2s: 33.204 [31.353, 33.554]
1 MiB; 4096 B; decrypt; LRW-precompute: 10.358 [9.990, 10.787]
1 MiB; 4096 B; decrypt; LRW-Horner: 8.627 [8.467, 8.743]
1 MiB; 4096 B; encrypt; AES-ECB · bulk: 1243.639 [1144.812, 1295.765]
1 MiB; 4096 B; encrypt; AES-XTS · OpenSSL whole-sector: 830.633 [772.229, 882.669]
1 MiB; 4096 B; encrypt; AES-XTS · manual, AES-NI requested: 55.931 [54.993, 58.276]
1 MiB; 4096 B; encrypt; XEX · keyed BLAKE2s: 6.915 [6.786, 7.230]
1 MiB; 4096 B; encrypt; AES-MAC-CBC: 4.751 [4.616, 4.977]
1 MiB; 4096 B; encrypt; LRW-precompute: 4.671 [4.532, 4.926]
1 MiB; 4096 B; encrypt; LRW-Horner: 4.157 [4.070, 4.328]
4 MiB; 512 B; decrypt; AES-ECB · bulk: 240.575 [234.895, 245.287]
4 MiB; 512 B; decrypt; AES-XTS · OpenSSL whole-sector: 141.946 [138.150, 147.773]
4 MiB; 512 B; decrypt; AES-MAC-CBC: 41.809 [41.441, 42.947]
4 MiB; 512 B; decrypt; AES-XTS · manual, AES-NI requested: 34.593 [34.029, 35.280]
4 MiB; 512 B; decrypt; XEX · keyed BLAKE2s: 25.407 [25.098, 25.981]
4 MiB; 512 B; decrypt; LRW-precompute: 9.202 [9.191, 9.587]
4 MiB; 512 B; decrypt; LRW-Horner: 7.922 [7.836, 8.155]
4 MiB; 512 B; encrypt; AES-ECB · bulk: 236.466 [223.948, 248.836]
4 MiB; 512 B; encrypt; AES-XTS · OpenSSL whole-sector: 133.457 [128.359, 137.402]
4 MiB; 512 B; encrypt; AES-XTS · manual, AES-NI requested: 34.750 [34.141, 35.744]
4 MiB; 512 B; encrypt; XEX · keyed BLAKE2s: 6.833 [6.741, 7.145]
4 MiB; 512 B; encrypt; LRW-precompute: 4.596 [4.501, 4.859]
4 MiB; 512 B; encrypt; AES-MAC-CBC: 4.519 [4.456, 4.768]
4 MiB; 512 B; encrypt; LRW-Horner: 4.160 [4.062, 4.270]
4 MiB; 4096 B; decrypt; AES-ECB · bulk: 1338.057 [1214.718, 1377.634]
4 MiB; 4096 B; decrypt; AES-XTS · OpenSSL whole-sector: 926.773 [872.061, 952.387]
4 MiB; 4096 B; decrypt; AES-MAC-CBC: 251.505 [242.902, 259.438]
4 MiB; 4096 B; decrypt; AES-XTS · manual, AES-NI requested: 57.320 [56.200, 59.911]
4 MiB; 4096 B; decrypt; XEX · keyed BLAKE2s: 34.171 [33.352, 35.208]
4 MiB; 4096 B; decrypt; LRW-precompute: 10.373 [10.000, 10.969]
4 MiB; 4096 B; decrypt; LRW-Horner: 8.636 [8.562, 8.913]
4 MiB; 4096 B; encrypt; AES-ECB · bulk: 1358.184 [1315.651, 1391.523]
4 MiB; 4096 B; encrypt; AES-XTS · OpenSSL whole-sector: 878.705 [863.710, 917.216]
4 MiB; 4096 B; encrypt; AES-XTS · manual, AES-NI requested: 57.778 [56.883, 60.541]
4 MiB; 4096 B; encrypt; XEX · keyed BLAKE2s: 6.999 [6.861, 7.315]
4 MiB; 4096 B; encrypt; AES-MAC-CBC: 4.750 [4.650, 4.996]
4 MiB; 4096 B; encrypt; LRW-precompute: 4.688 [4.620, 4.953]
4 MiB; 4096 B; encrypt; LRW-Horner: 4.148 [4.133, 4.345]
