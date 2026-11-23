# What do encrypted disk snapshots reveal?

One 64 × 64 grayscale penguin fills a 4 KiB sector. Each 4 × 4 tile is one 16-byte AES block. Red outlines show which blocks differ between two writes to the same address under the same key.

![Two writes: XTS isolates the eye, belly and foot; XEX shows one changed suffix](figure/blink.gif)

## 1. Equality patterns and the longest common prefix

An **equality pattern** identifies which blocks have the same value without revealing that value. For two writes $P$ and $Q$, each containing $n$ blocks, the **longest common prefix** counts consecutive matching blocks from the start of the sector:

$$
\operatorname{LCP}(P,Q)=\max\{k\in\{0,\ldots,n\}: P_i=Q_i\text{ for every }0\le i<k\}.
$$

| Scheme | What an observer learns from ciphertext |
|---|---|
| AES-ECB | Equal plaintext blocks are recognisable anywhere on the disk while the key stays fixed. |
| AES-XTS | At the same sector and block index, equal ciphertext across writes means equal plaintext, and conversely. Every changed position is visible. |
| CBC-Ratchet | The ciphertext LCP equals the plaintext LCP, revealing the first changed block, if any. |
| CTR-Ratchet | The same LCP, plus the exact plaintext XOR through the first differing block because the pad repeats up to and including that block. |
| XEX-Ratchet | The ciphertext LCP equals the plaintext LCP. At the first edit both writes still use the same mask; thereafter the changed predecessor feeds the next mask. Later ciphertext differences need not indicate further plaintext edits. |

## 2. What the penguin shows

**One snapshot.** The plaintext has five distinct tile values. ECB preserves their repetitions and exposes the silhouette; XTS produced 256 distinct ciphertext tiles.

![Plaintext, ECB and XTS with their repeated-block patterns](figure/02-one-snapshot.png)

**Two snapshots.** XTS marked exactly 15 edited tiles: one eye, a 13-tile heart and one foot. All six XEX variants marked tiles 89–255, giving **LCP = 89**. Editing the eye alone produced the same XEX outline: the observer could locate the first edit but could not infer the other two from that outline.

![Three local XTS edits versus one continuous XEX suffix](figure/03-two-snapshots.png)

**Mask control.** Only the keyed mask function changes across the six XEX panels. CBC-Ratchet and CTR-Ratchet above are theoretical comparisons.

![Same sector under six keyed XEX masks](figure/01-mask-control.png)

## Reproduce

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python run.py
```

Figures are written to `figure/`; [block indices](evidence/two-writes.csv) are recorded for each comparison. The demo uses public fixture keys; the ECB key was selected for image contrast.
