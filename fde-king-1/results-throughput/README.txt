FDE King 1 run summary
Requested fresh-process sessions: 6
CPU: 13th Gen Intel(R) Core(TM) i7-1365U; logical CPUs: 12; affinity: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
OS: Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.43; Python: 3.14.4; GIL: True
Backend: OpenSSL 4.0.1 9 Jun 2026; AES-NI available: True; CLMUL available: True
RQ1-3 calling threads: 1; RQ4 worker counts: [1, 2, 4]; thread batches KiB: [256]
Working sets MiB: [1.0]; sector sizes: [512, 4096]; throughput trials/condition/launch: 5
RQs: [2]; schemes: ecb_bulk, xts_manual_soft, xts_manual_ni, xts_library, xex_blake2s, xex_blake2b, xex_blake3, xex_siphash128, xex_kmac128, cbc_mac, lrw_horner, lrw_precompute
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
1 MiB; 512 B; decrypt; AES-ECB · bulk: 249.552 [245.518, 255.813]
1 MiB; 512 B; decrypt; AES-XTS · OpenSSL whole-sector: 148.032 [141.229, 152.349]
1 MiB; 512 B; decrypt; AES-MAC-CBC: 40.718 [38.619, 41.900]
1 MiB; 512 B; decrypt; AES-XTS · manual, AES-NI requested: 32.901 [32.265, 34.085]
1 MiB; 512 B; decrypt; AES-XTS · manual, AES-NI off: 30.524 [28.183, 30.737]
1 MiB; 512 B; decrypt; XEX · keyed BLAKE2s: 24.494 [23.114, 24.913]
1 MiB; 512 B; decrypt; XEX · keyed BLAKE3: 22.783 [21.245, 23.278]
1 MiB; 512 B; decrypt; XEX · keyed BLAKE2b: 22.025 [21.564, 22.119]
1 MiB; 512 B; decrypt; XEX · SipHash-2-4-128: 15.741 [15.525, 16.417]
1 MiB; 512 B; decrypt; LRW-precompute: 9.117 [8.767, 9.277]
1 MiB; 512 B; decrypt; LRW-Horner: 7.908 [7.528, 7.986]
1 MiB; 512 B; decrypt; XEX · KMAC128: 1.955 [1.851, 1.987]
1 MiB; 512 B; encrypt; AES-ECB · bulk: 251.861 [235.616, 254.450]
1 MiB; 512 B; encrypt; AES-XTS · OpenSSL whole-sector: 141.364 [113.573, 146.286]
1 MiB; 512 B; encrypt; AES-XTS · manual, AES-NI requested: 33.442 [32.797, 33.928]
1 MiB; 512 B; encrypt; AES-XTS · manual, AES-NI off: 30.203 [29.721, 30.758]
1 MiB; 512 B; encrypt; XEX · keyed BLAKE2s: 6.809 [6.572, 7.034]
1 MiB; 512 B; encrypt; XEX · keyed BLAKE2b: 6.468 [6.395, 6.697]
1 MiB; 512 B; encrypt; XEX · keyed BLAKE3: 6.092 [6.008, 6.335]
1 MiB; 512 B; encrypt; XEX · SipHash-2-4-128: 5.625 [5.520, 5.802]
1 MiB; 512 B; encrypt; LRW-precompute: 4.618 [4.458, 4.681]
1 MiB; 512 B; encrypt; AES-MAC-CBC: 4.497 [4.396, 4.598]
1 MiB; 512 B; encrypt; LRW-Horner: 4.155 [4.000, 4.348]
1 MiB; 512 B; encrypt; XEX · KMAC128: 1.579 [1.517, 1.601]
1 MiB; 4096 B; decrypt; AES-ECB · bulk: 1257.268 [1051.920, 1286.442]
1 MiB; 4096 B; decrypt; AES-XTS · OpenSSL whole-sector: 858.338 [808.706, 889.701]
1 MiB; 4096 B; decrypt; AES-MAC-CBC: 257.309 [250.193, 265.833]
1 MiB; 4096 B; decrypt; AES-XTS · manual, AES-NI requested: 55.484 [53.670, 56.233]
1 MiB; 4096 B; decrypt; AES-XTS · manual, AES-NI off: 48.291 [45.121, 48.992]
1 MiB; 4096 B; decrypt; XEX · keyed BLAKE2s: 32.099 [29.465, 33.104]
1 MiB; 4096 B; decrypt; XEX · keyed BLAKE3: 29.513 [28.767, 30.856]
1 MiB; 4096 B; decrypt; XEX · keyed BLAKE2b: 27.885 [26.910, 28.736]
1 MiB; 4096 B; decrypt; XEX · SipHash-2-4-128: 18.902 [18.167, 19.260]
1 MiB; 4096 B; decrypt; LRW-precompute: 10.353 [9.759, 10.414]
1 MiB; 4096 B; decrypt; LRW-Horner: 8.469 [8.253, 8.887]
1 MiB; 4096 B; decrypt; XEX · KMAC128: 2.000 [1.962, 2.029]
1 MiB; 4096 B; encrypt; AES-ECB · bulk: 1188.813 [1026.696, 1255.565]
1 MiB; 4096 B; encrypt; AES-XTS · OpenSSL whole-sector: 845.432 [799.838, 876.822]
1 MiB; 4096 B; encrypt; AES-XTS · manual, AES-NI requested: 55.393 [55.150, 57.750]
1 MiB; 4096 B; encrypt; AES-XTS · manual, AES-NI off: 48.417 [46.339, 49.068]
1 MiB; 4096 B; encrypt; XEX · keyed BLAKE2s: 6.884 [6.765, 7.043]
1 MiB; 4096 B; encrypt; XEX · keyed BLAKE2b: 6.633 [6.474, 6.872]
1 MiB; 4096 B; encrypt; XEX · keyed BLAKE3: 6.183 [6.103, 6.437]
1 MiB; 4096 B; encrypt; XEX · SipHash-2-4-128: 5.630 [5.408, 5.850]
1 MiB; 4096 B; encrypt; LRW-precompute: 4.704 [4.450, 4.743]
1 MiB; 4096 B; encrypt; AES-MAC-CBC: 4.675 [4.585, 4.811]
1 MiB; 4096 B; encrypt; LRW-Horner: 4.240 [4.069, 4.343]
1 MiB; 4096 B; encrypt; XEX · KMAC128: 1.595 [1.561, 1.621]
