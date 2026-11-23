| Construction | Enc MiB/s | Dec MiB/s | Enc ns/sector | Enc ns/byte |
| --- | --- | --- | --- | --- |
| AES-ECB · bulk | 1237.87 | 1364.66 | 3,156 | 0.77 |
| AES-XTS · OpenSSL, full sector | 853.43 | 881.17 | 4,578 | 1.12 |
| AES-XTS · manual, AES-NI enabled | 51.70 | 52.42 | 75,561 | 18.45 |
| AES-XTS · manual, AES-NI off | 47.77 | 47.14 | 81,774 | 19.96 |
| XEX · keyed BLAKE2s | 6.25 | 32.18 | 625,016 | 152.59 |
| XEX · keyed BLAKE2b | 5.89 | 17.90 | 662,649 | 161.78 |
| XEX · SipHash-2-4-128 | 4.91 | 16.46 | 796,347 | 194.42 |
| AES-MAC-CBC | 3.84 | 51.95 | 1,017,243 | 248.35 |
| XEX · keyed BLAKE3 | 3.84 | 18.69 | 1,018,459 | 248.65 |
| LRW-Polynomial | 3.58 | 7.36 | 1,092,607 | 266.75 |
| XEX · KMAC128 | 1.41 | 1.74 | 2,777,177 | 678.02 |
