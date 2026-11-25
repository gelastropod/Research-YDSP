# Penguin snapshot demonstrations

The inputs are the supplied [64×64 RGBA PNG](assets/snapshot-1.png) and its [edited version](assets/snapshot-2.png). Exactly 86 decoded pixels differ: 30 at the eye on the viewer's left and 56 in the heart patch. Both snapshots are encrypted at the same starting sector address with the same keys. The experiment encrypts image payloads, not PNG file bytes.

| Case | Payload | 4 KiB sectors | One 16-byte AES block represents |
|---|---:|---:|---|
| `bc3` | 4 KiB | 1 | One 4×4 BC3 texture tile. |
| `rgba` | 16 KiB | 4 | Four adjacent RGBA pixels. Each sector spans 16 rows. |
| `rgba256` (bonus) | 256 KiB | 64 | Four adjacent RGBA pixels. Each sector spans 4 rows. Both inputs were upscaled with Lanczos before encoding. |

BC3 excludes the 128-byte DDS header from the encrypted payload. For previews, the decoder interprets the ciphertext as BC3, then composites on white. The RGBA previews show ciphertext RGB opaquely. All equality and difference checks use every byte, including bytes omitted from the preview.

## Figures

Each [BC3](results/bc3/), [RGBA](results/rgba/) and [RGBA 256](results/rgba256/) folder contains the same set, typeset with LaTeX:

1. **Attack 1, ECB vs AES-XTS.** The first row shows the actual payload previews. The second row shows dominant equality classes: the six most frequent repeated block values get distinct colours, other repeated values are grey, and unique blocks are near-white. No plaintext labels are used in ciphertext classification.
2. **Attack 2 demonstrated.** Write 1 and Write 2 under plaintext, AES-XTS and the BLAKE3 XEX ratchet. Red lines trace changed-block regions on both writes. The included **blink GIF** alternates these previews with the same outlines and one shared palette.
3. **Attack 2 differences.** White marks a nonzero 16-byte XOR; black marks exact equality. Blue dotted lines show sector boundaries. The second row shows the number of set bits in each block XOR, using one fixed 0–128 scale.
4. **Different hashes in Attack 2.** Write 2 ciphertext and the changed-block map for BLAKE3, BLAKE2s, HMAC-SHA256, AES-CMAC, KMAC128 and GHASH. These are alternatives for the XEX mask, not six encryption modes or a comparative security proof.

Each case also includes both raw payload snapshots for every scheme and CSVs with block counts and first changes per sector.

## Results for this input pair

| Case | Blocks with a duplicate in ECB, write 2 | Changed plaintext and XTS blocks | Changed XEX blocks (each variant) | Sectors containing edits |
|---|---:|---:|---:|---:|
| BC3 64×64 | 124 / 256 | 12 | 218 | 1 / 1 |
| RGBA 64×64 | 582 / 1,024 | 33 | 558 | 3 / 4 |
| RGBA 256×256 | 10,397 / 16,384 | 816 | 5,537 | 25 / 64 |

XTS produced no duplicate blocks in write 2 in these runs. In the two-write comparison, it identifies the exact changed block positions. The ratchet preserves the common prefix within each sector and changed the rest of each affected sector in these runs. It still reveals which sectors were touched and where each sector's first edit occurred. The larger RGBA example makes the sector resets especially visible. Counts across encodings are not directly comparable as the blocks represent different sets of pixels.

## Reproduce

With Python 3, LaTeX (`pdflatex` plus `graphicx`) and Poppler (`pdftoppm`) on PATH:

```sh
python -m pip install -r requirements.txt
python run.py
python run.py --case rgba256
```

`python run.py --case bc3` and `--case rgba` regenerate one case. `--output path` selects a different output directory. The runner checks the input edits, decryption round trips, exact ECB/XTS difference positions and each ratchet's first divergence. The keys are fixed demonstration fixtures. One snapshot by itself does not measure leakage across repeated sector writes.
