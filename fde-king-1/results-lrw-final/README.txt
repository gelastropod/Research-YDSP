FDE King 1 run summary
Requested fresh-process sessions: 6
CPU: INTEL(R) XEON(R) PLATINUM 8573C; logical CPUs: 9; affinity: [0, 1, 2, 3, 4, 5, 6, 7, 8]
OS: Linux-6.18.57-x86_64-with-glibc2.41; Python: 3.12.14; GIL: True
Backend: OpenSSL 4.0.1 9 Jun 2026; AES-NI available: True; CLMUL available: True
RQ1-3 calling threads: 1; RQ4 worker counts: [1, 2]; thread batches KiB: [16.0, 64.0]
Working sets MiB: [0.0625, 0.25]; sector sizes: [512, 4096]; throughput trials/condition/launch: 10
RQs: [1, 2, 3, 4]; schemes: lrw_horner, lrw_precompute
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
0.0625 MiB; 512 B; decrypt; LRW-precompute: 5.144 [4.838, 5.569]
0.0625 MiB; 512 B; decrypt; LRW-Horner: 4.507 [4.193, 4.701]
0.0625 MiB; 512 B; encrypt; LRW-precompute: 2.494 [2.291, 2.614]
0.0625 MiB; 512 B; encrypt; LRW-Horner: 2.202 [2.067, 2.400]
0.0625 MiB; 4096 B; decrypt; LRW-precompute: 5.820 [5.317, 6.193]
0.0625 MiB; 4096 B; decrypt; LRW-Horner: 4.819 [4.397, 5.149]
0.0625 MiB; 4096 B; encrypt; LRW-precompute: 2.531 [2.336, 2.595]
0.0625 MiB; 4096 B; encrypt; LRW-Horner: 2.260 [2.098, 2.372]
0.25 MiB; 512 B; decrypt; LRW-precompute: 5.006 [4.696, 5.483]
0.25 MiB; 512 B; decrypt; LRW-Horner: 4.366 [4.062, 4.657]
0.25 MiB; 512 B; encrypt; LRW-precompute: 2.451 [2.263, 2.560]
0.25 MiB; 512 B; encrypt; LRW-Horner: 2.212 [1.973, 2.355]
0.25 MiB; 4096 B; decrypt; LRW-precompute: 5.759 [5.300, 6.059]
0.25 MiB; 4096 B; decrypt; LRW-Horner: 4.781 [4.334, 4.982]
0.25 MiB; 4096 B; encrypt; LRW-precompute: 2.535 [2.249, 2.661]
0.25 MiB; 4096 B; encrypt; LRW-Horner: 2.160 [2.111, 2.425]
