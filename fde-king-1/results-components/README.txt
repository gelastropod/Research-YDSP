FDE King 1 run summary
Requested fresh-process sessions: 6
CPU: 13th Gen Intel(R) Core(TM) i7-1365U; logical CPUs: 12; affinity: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
OS: Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.43; Python: 3.14.4; GIL: True
Backend: OpenSSL 4.0.1 9 Jun 2026; AES-NI available: True; CLMUL available: True
RQ1-3 calling threads: 1; RQ4 worker counts: [1, 2, 4]; thread batches KiB: [256]
Working sets MiB: [1]; sector sizes: [512, 4096]; throughput trials/condition/launch: 10
RQs: [1, 3]; schemes: ecb_bulk, xts_manual_soft, xts_manual_ni, xts_library, xex_blake2s, xex_blake2b, xex_blake3, xex_siphash128, xex_kmac128, cbc_mac, lrw_horner, lrw_precompute
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
