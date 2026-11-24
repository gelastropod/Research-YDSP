# What do two encrypted snapshots of a penguin reveal?

The penguin is a **64 × 64 BC3 (DXT5) texture**. In this graphics format, one 4 × 4 square of pixels occupies exactly 16 encoded bytes: **one square = one AES block**. There are 16 squares per row, 16 rows, and 4,096 bytes in total. The red outlines trace blocks whose 16 bytes actually changed.

![Blink between the two writes; red outlines stay fixed on both frames](figure/blink.gif)

## 1. Method: from a sector to a picture

1. Encode each version as a [BC3 texture](https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression). Place the 4 KiB texture payload at the start of sector 37; the 128-byte DDS header is viewing metadata, outside the simulated sector. This models an aligned texture payload, not an arbitrary DDS file copied to disk.
2. Encrypt the **stored bytes in order**, reusing the same address and keys for both writes. Block $j$ (zero-based) contains bytes $16j$ through $16j+15$ and starts at pixel $(4(j\bmod16),4\lfloor j/16\rfloor)$. No extra padding, Hilbert traversal or encryption of individual pixels is needed.
3. Put the same header on each ciphertext payload and decode it as BC3. All panels use the same decoder and grey background for transparency. The comparison uses **all 16 ciphertext bytes**, never a pixel colour or a visual estimate. Red lines follow only the outer edges of the changed tiles. The GIF uses a fixed palette and outlines on both frames.

## 2. Equality and longest common prefix

For two writes $P,Q$ of $n$ blocks, their longest common prefix is

$$
\operatorname{LCP}(P,Q)=\max\{k\in\{0,\ldots,n\}: P_i=Q_i\ \text{for all}\ 0\le i<k\}.
$$

| Mode | What ciphertext equality tells us |
|---|---|
| AES-ECB | Equal plaintext blocks encrypt identically wherever they occur under the key. A single snapshot can reveal a silhouette. |
| AES-XTS | At the **same sector and position** under the same keys, ciphertext is equal across writes exactly when plaintext is equal. Comparing snapshots locates every edited block. |
| XEX ratchet | The ciphertext and plaintext have the same LCP. Identical prefixes give identical masks; at the first edit, encryption under the same mask is a permutation, so ciphertext differs. The changed predecessor can then change the next mask even when the next plaintext is unchanged. |

## 3. Results

**One snapshot.** All 256 plaintext blocks belong to just five repeated values. ECB reproduces the penguin’s outline in the decoded ciphertext and preserves all five equality classes. XTS produced 256 distinct blocks. The lower panels colour identical byte strings alike; they corroborate what the upper panels show directly.

![One write: decoded textures above; full-block equality classes below](figure/02-one-snapshot.png)

**Two snapshots.** We blinked one eye (1 tile), added a heart on the belly (13), and marked one foot (1). XTS flagged exactly these 15 tiles. With each of the six XEX masks, the first **89 blocks** stayed unchanged and all **167 remaining blocks** differed. Editing the eye alone gave the same XEX outline, so that outline cannot establish whether the belly or foot was edited. Equality of the LCP is exact; the uninterrupted changed suffix is a measured result for this fixture, not a security proof.

![Two writes: XTS outlines three edits and XEX outlines the suffix starting at the eye](figure/03-two-snapshots.png)

**Mask control.** These six views change only the keyed mask function: BLAKE3, BLAKE2s, HMAC-SHA256, AES-CMAC, KMAC128 and GHASH. Each uses the same AES data key and the same input layout: 16-byte sector number, 16-byte block index, and previous 16-byte ciphertext (zero at the start). Similar pictures do not establish equivalent security.

![Same plaintext, address and AES data key across six XEX mask choices](figure/01-mask-control.png)

## Reproduce

From the extracted project directory:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run.py
```

The run verifies decryption, compares full blocks, and checks that visible changes in the saved GIF match the measured block sets. See [one-write counts](evidence/one-write.csv), [two-write block indices](evidence/two-writes.csv), or the [DDS files and their PNG previews](rasters/). All keys are public demonstration fixtures. The penguin uses flat fills to make repeated blocks visible; arbitrary photos need not show such a clear ECB silhouette.
