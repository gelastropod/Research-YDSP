| Construction | Enc MiB/s | Dec MiB/s | Enc ns/sector | Enc ns/byte |
| --- | --- | --- | --- | --- |
| AES-ECB · bulk | 1172.21 | 1213.95 | 3,333 | 0.81 |
| AES-XTS · OpenSSL, full sector | 665.59 | 725.46 | 5,870 | 1.43 |
| AES-XTS · manual, AES-NI off | 35.49 | 33.79 | 110,061 | 26.87 |
| AES-XTS · manual, AES-NI enabled | 34.84 | 40.81 | 112,357 | 27.43 |
| XEX · keyed BLAKE2s | 4.41 | 23.21 | 886,712 | 216.48 |
| XEX · keyed BLAKE2b | 4.28 | 20.30 | 912,176 | 222.70 |
| XEX · keyed BLAKE3 | 4.11 | 23.05 | 951,556 | 232.31 |
| XEX · SipHash-2-4-128 | 3.92 | 12.62 | 996,243 | 243.22 |
| AES-MAC-CBC | 2.98 | 43.90 | 1,310,457 | 319.94 |
| LRW-Polynomial | 2.63 | 6.23 | 1,486,998 | 363.04 |
| XEX · KMAC128 | 1.06 | 1.37 | 3,701,698 | 903.73 |
