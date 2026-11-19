| Construction | Enc MiB/s | Dec MiB/s | Enc ns/sector | Enc ns/byte |
| --- | --- | --- | --- | --- |
| AES-ECB · bulk | 795.58 | 859.31 | 4,924 | 1.20 |
| AES-XTS · OpenSSL, full sector | 507.50 | 430.43 | 7,701 | 1.88 |
| AES-XTS · manual, AES-NI enabled | 27.24 | 27.09 | 143,387 | 35.01 |
| AES-XTS · manual, AES-NI off | 23.88 | 24.37 | 163,585 | 39.94 |
| XEX · keyed BLAKE2s | 3.33 | 20.02 | 1,174,058 | 286.64 |
| XEX · keyed BLAKE3 | 2.91 | 15.52 | 1,344,531 | 328.25 |
| XEX · keyed BLAKE2b | 2.64 | 15.90 | 1,482,823 | 362.02 |
| LRW-Polynomial | 2.14 | 4.59 | 1,829,992 | 446.78 |
| AES-MAC-CBC | 2.06 | 31.10 | 1,893,374 | 462.25 |
| XEX · SipHash-2-4-128 | 1.98 | 7.99 | 1,971,416 | 481.30 |
| XEX · KMAC128 | 0.58 | 0.85 | 6,792,787 | 1658.40 |
