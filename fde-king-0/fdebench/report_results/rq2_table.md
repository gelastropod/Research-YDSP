| Construction | Enc MiB/s | Dec MiB/s | Enc ns/sector | Enc ns/byte |
| --- | --- | --- | --- | --- |
| AES-ECB · bulk | 1107.98 | 1182.61 | 3,526 | 0.86 |
| AES-XTS · OpenSSL, full sector | 636.81 | 712.32 | 6,136 | 1.50 |
| AES-XTS · manual, AES-NI enabled | 35.63 | 39.25 | 109,884 | 26.83 |
| AES-XTS · manual, AES-NI off | 34.14 | 34.54 | 114,463 | 27.95 |
| XEX · keyed BLAKE2b | 4.77 | 20.43 | 819,360 | 200.04 |
| XEX · keyed BLAKE2s | 4.75 | 24.56 | 821,925 | 200.67 |
| XEX · keyed BLAKE3 | 4.46 | 23.58 | 875,298 | 213.70 |
| XEX · SipHash-2-4-128 | 3.94 | 13.95 | 991,470 | 242.06 |
| AES-MAC-CBC | 3.05 | 46.12 | 1,282,299 | 313.06 |
| LRW-Polynomial | 2.75 | 5.95 | 1,419,898 | 346.65 |
| XEX · KMAC128 | 1.07 | 1.36 | 3,644,972 | 889.89 |
