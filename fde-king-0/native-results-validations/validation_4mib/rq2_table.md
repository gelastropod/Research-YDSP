| Construction | Enc MiB/s | Dec MiB/s | Enc ns/sector | Enc ns/byte |
| --- | --- | --- | --- | --- |
| AES-XTS · OpenSSL, full sector | 958.91 | 1040.57 | 4,074 | 0.99 |
| AES-ECB · bulk | 860.23 | 1020.91 | 4,559 | 1.11 |
| AES-XTS · manual, AES-NI enabled | 63.69 | 63.90 | 61,336 | 14.97 |
| AES-XTS · manual, AES-NI off | 20.15 | 32.68 | 194,278 | 47.43 |
| XEX · keyed BLAKE2s | 6.19 | 30.96 | 630,729 | 153.99 |
| XEX · keyed BLAKE2b | 5.97 | 26.27 | 653,948 | 159.66 |
| XEX · keyed BLAKE3 | 5.65 | 28.31 | 690,966 | 168.69 |
| XEX · SipHash-2-4-128 | 5.16 | 17.57 | 756,463 | 184.68 |
| AES-MAC-CBC | 4.10 | 62.93 | 951,830 | 232.38 |
| LRW-Polynomial | 3.74 | 7.34 | 1,045,685 | 255.29 |
| XEX · KMAC128 | 1.27 | 1.74 | 3,068,148 | 749.06 |
