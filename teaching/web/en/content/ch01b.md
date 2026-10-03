# Chapter 1½ · What is JPEG? What is a DCT coefficient? (The compressed-domain battlefield)

<!-- lang-switch -->
> [🌐 中文版本](https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/ch01b.html)




> **Beginner note｜** This chapter was added in v1.9.0 (2026-10) in response to the feedback that the learning path should explain JPEG and DCT *before* LSB and steganography. It is numbered "1½" rather than renumbering every later chapter: the handbook has many "see chapter N" cross-references, ten per-chapter notebooks, and a fact-checking script — renumbering would cost far more than it gains. Read it after chapter 1 and before chapter 3.

Chapter 1 split an image into pixels and bit planes. The natural next step is LSB steganography. But nsF5 has two homes in this project: the pixel-domain implementation in `ns5_core.py` (main repo, modifies grayscale pixels), and — since v1.9.0 — the JPEG compressed-domain implementation (modifies quantized DCT coefficients, from the sister project yccstego, now bridged into the mainline). Textbook F5/nsF5 is the latter. Without understanding JPEG and DCT coefficients, the "+3→+2" in chapters 4 and 5 stays a slogan.

## 1.5.1 What is JPEG: a "lossy compressor"

JPEG is not just a file format; it is a **lossy compression pipeline** applied to every 8×8 pixel block:

1. **DCT transform**: rewrite the 8×8 pixel values as 64 "pattern weights" (next section);
2. **Quantization**: divide each weight by a step size from the quantization table and round — **this is where loss happens**: the bottom-right (high-frequency) steps are large, so rounding zeroes out most of them;
3. **Entropy coding**: serialize the surviving non-zero coefficients in zig-zag order and write the .jpg file.

Step 3 is reversible (you can decode it bit-exactly); step 2 is not (rounded information is gone). **All of compressed-domain steganography lives inside the product of step 2 — the quantized coefficients.**

> **Pitfall｜** This explains the chapter-3 FAQ line "JPEG destroys pixel LSBs": saving an LSB-stego PNG as JPEG re-runs the whole pipeline and quantization scrambles the LSB structure. Conversely, compressed-domain steganography writes the quantized coefficients themselves, and the encoder carries them faithfully through entropy coding — so the stego image **must remain a JPEG** and must **never be re-saved by another tool** (re-saving re-quantizes and destroys the payload). This is why the GUI saves JPEG-domain stego images as raw bytes.

## 1.5.2 What is a DCT coefficient: the "recipe" of an 8×8 block

Think of an 8×8 block as a tiny picture. The DCT (discrete cosine transform) provides 64 fixed "patterns": the top-left pattern is a uniform brightness (lowest frequency), and patterns get finer toward the bottom-right (high frequency). The DCT answers one question: **in what proportions must these 64 patterns be mixed to produce this block?** Those 64 proportions are the DCT coefficients.

- The first (top-left) coefficient is the **DC** term: the block's average brightness. It never carries the message;
- The other 63 are **AC** coefficients;
- Natural images concentrate energy in the top-left, so quantization zeroes out most bottom-right coefficients — **zeroed cells are not carriers; the surviving non-zero AC coefficients are**.

> **Hands-on｜** The snippet below uses the very same DCT matrix and quantization table as the project's compressed-domain implementation (`yccstego/dct.py`) to quantize one 8×8 block at qualities 60, 85 and 95, counting non-zero AC carriers and |c|=1 "wet" points. Install the dependency first: `pip install yccstego`.

```python
import numpy as np
from yccstego import dct as jdct

# Build an 8x8 block: smooth gradient (low frequency) + light noise (high)
rng = np.random.default_rng(3)
block = np.linspace(90, 200, 8)[None, :] + np.linspace(0, 60, 8)[:, None]
block = np.clip(block + rng.integers(-8, 9, (8, 8)), 0, 255).astype(float)

counts = {}
for q in (60, 85, 95):
    T = jdct.scale_qtable(jdct.LUM_QT, q)      # libjpeg-style quality scaling
    F = jdct.dct_blocks(block - 128)           # level shift, then DCT (JPEG way)
    Q = np.round(F / T).astype(int)            # quantization: loss happens here
    ac = Q.reshape(-1)[1:]                     # drop DC, 63 AC coefficients left
    nz = int(np.sum(ac != 0))
    wet = int(np.sum(np.abs(ac) == 1))
    counts[q] = nz
    print(f"quality {q}: {nz} non-zero AC carriers, {wet} wet (|c|=1) points")
assert counts[95] > counts[60], "higher quality must leave more carriers"
print(f"quality 95 leaves more non-zero AC carriers than quality 60: {counts[95]} > {counts[60]}")
```

<!-- expect: quality 95 leaves more non-zero AC carriers than quality 60 -->

> **Observe｜** Two patterns: raising quality from 60 to 95 visibly increases the carriers (smaller steps let more coefficients survive), and there are plenty of |c|=1 coefficients — which are about to cause trouble.

## 1.5.3 nsF5 on coefficients: carriers, wet points, decrements

In JPEG-domain nsF5 the carriers are the **non-zero AC coefficients of quantized luma (Y) blocks**, each contributing one bit: `x = c & 1` (parity). Writing a bit is not a flip but **F5's decrement: subtract 1 from the magnitude, keep the sign**.

| Coefficient | After | Note |
| --- | --- | --- |
| +3 | +2 | magnitude -1, parity flips |
| −5 | −4 | sign preserved, LSB flipped |
| +1 | wet, untouched | decrementing would hit 0 (shrinkage): it would vanish from the carrier set |
| −1 | wet, untouched | same |

Why shrinkage is a disaster: the extractor collects carriers in the same order; one coefficient shrinking from +1 to 0 removes it from the set and misaligns every later bit. That is F5's classic flaw, and exactly what nsF5 fixes with **wet-paper coding** (mark |c|=1 coefficients wet, solve on dry points) — chapter 5.

> **Hands-on｜** Three lines to see the decrement/wet boundary:

```python
for c in (3, -5, 1, -1):
    action = c - (1 if c > 0 else -1) if abs(c) > 1 else "wet, untouched"
    print(c, "->", action)
```

<!-- expect: 3 -> 2 -->

> **Think｜**
> 1. +3 and +2 share the same binary LSB of 1 — how does decrementing flip the bit at all? Hint: think about parity near zero, and why |c|=1 must not be decremented.
> 2. Compared with flipping (jumping between +3 and +4), decrementing piles magnitude around |c|=1. Is that pile-up the price of stealth, or its loophole? Chapter 8's "magnitude-1 fingerprint" turns it into a detector.

> **Pitfall｜** Keying works as in the pixel domain: the hiding path derives from "chroma-coefficient hash + password"; a mismatched p / password / quality makes extraction fail. The re-run contract is now identical in both domains: since yccstego 0.2.0 the wet-paper search seed derives from the input, so embedding is byte-deterministic; the experiment record stores the yccstego version used — re-runs on the same version get byte-level checks, and cross-version records fall back to "extraction matches" (older records stay compatible), as documented in `src/experiment.py`.

## 1.5.4 Run it on a real JPEG

The two snippets above looked at one block. Real embedding is done by yccstego: split the whole image, quantize block by block, run syndrome coding over all carriers, then entropy-code back to a standard .jpg. The bridge below drives exactly that (the GUI's JPEG domain and the CLI's `--jpeg` call the same code):

```python
import sys
sys.path.insert(0, "src")        # needed for source runs; drop after pip install
import numpy as np
import jpegstego

rng = np.random.default_rng(7)
y = np.linspace(0, 220, 128)[None, :]
x = np.linspace(0, 90, 128)[:, None]
gray = np.clip(110 + y + x + rng.integers(-6, 7, (128, 128)), 0, 255).astype(np.uint8)
rgb = np.stack([gray, gray, gray], axis=-1)      # the JPEG domain eats RGB

jpg, rep = jpegstego.embed_jpeg(rgb, "Hello, DCT domain!", p=3, quality=85)
print("changed coefficients:", rep["carriers_changed"], "capacity(bit):", rep["capacity_bits"])

msg, _, tampered, head_match = jpegstego.extract_jpeg(jpg, p=3)
assert msg == "Hello, DCT domain!" and not tampered and head_match
print("round-trip matches:", msg)
```

<!-- expect: round-trip matches: Hello, DCT domain! -->

Command-line equivalent (after installation):

```bash
nsf5stego embed cover.png --jpeg -m "secret" --quality 85
nsf5stego extract cover_stego.jpg --jpeg
```

## 1.5.5 Back to the code

| Concept | File | Read first |
| --- | --- | --- |
| Bridge (unified entry / degradation) | src/jpegstego.py | embed_jpeg / extract_jpeg |
| Block-level nsF5 (decrement + wet paper) | yccstego/yccstego/nsf5.py | _embed_block / solve_wet_paper |
| DCT and quantization tables | yccstego/yccstego/dct.py | _dct_matrix / scale_qtable / LUM_QT |
| JPEG-domain analysis (\|c\|=1 fingerprint) | yccstego/yccstego/steganalysis.py | analyze_y |
| Re-run contract (two domains) | src/experiment.py | verify() and the module docstring |
| GUI domain switch | src/gui.py | _on_domain_change / _do_embed_jpeg |

> **Think｜** Embed the same 128×128 image once in the pixel domain (chapter 5's nsF5Pixel) and once in this chapter's JPEG domain, and count the writable positions: roughly 16,000 pixel bits versus a few thousand coefficients. What governs the gap? What happens at quality 60? This capacity intuition pays off in chapter 10's capstone.
