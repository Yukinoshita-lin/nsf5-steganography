# Appendix J - Exercise Hints and Answers

<!-- lang-switch -->
> [🌐 中文版](https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/appJ.html)



This appendix gives only "hints + key numbers"; work out the full reasoning yourself first — an exercise only counts once you have checked the answer. The problem numbers correspond to the end-of-chapter exercises of each chapter.

## J.1 Chapter 1

P1.1: 156 = 10011100₂, LSB = 0. Clear-then-set: 156 & 0xFE = 156, then | 1 → 157; XOR: 156 ^ 1 = 157. Both methods give the same result.

P1.2: After embedding [133, 132, 131, 129, 134, 130, 129, 135], with changes [+1, −1, +1, 0, 0, −1, +1, 0] (bit-for-bit identical to the table in Section 3.2).

P1.3: After random bits are embedded into an all-zero image, every pixel is rewritten somewhere between 0/1 — the histogram shifts from "concentrated at 0" to "half 0 and half 1", and the value pair (0,1) is flattened completely; visually it is still all black (value 1 ≈ black), but the chi-square statistic shoots up instantly. The visual redundancy is still there; the statistical redundancy is gone.

P1.4: The MSB plane is heavily skewed (for positive integers the MSB = 1 share is high), and the lower a bit plane is, the closer to 50% it gets — the LSB plane is the one that "looks most like a coin toss".

## J.2 Chapter 1½

P1½.1: Quantized DC = round(−224 / 5) = −45; dequantized, −45 × 5 = −225; reconstructed mean brightness = −225 ÷ 8 + 128 = 99.875, off from the original 100 by 0.125 — that is the concrete size of "lossy".

P1½.2: +3 → +2 is a decrement (magnitude −1, sign kept, LSB flipped); +3 → +4 also flips the LSB, but it is an **increment** — it pushes energy toward high frequencies, violates the nsF5 discipline of "minimal modification", and leaves a detectable "high-frequency boost" signature on the coefficient histogram. The first principle of steganographic modification: if the goal can be reached with the smallest, direction-certain change, do not introduce new statistical traces.

P1½.3: Higher quality → smaller quantization steps → fewer coefficients rounded to zero → more nonzero AC coefficients (carriers) → more capacity. Conversely, a low-quality JPEG is itself a "big cleanup".

P1½.4: Pixel-domain capacity ≈ 8 KB with 108 pixels modified; JPEG-domain capacity 2 205 bits with 117 coefficients modified — compare the table in Section 1.5.3.

## J.3 Chapter 2

P2.1: In uint8, 250 + 10 wraps around to 4; 3 − 5 underflows to 254 (modulo 256).

P2.2: b = a.copy() or b = np.array(a); for a copy, b.base is None, while for a view, b.base is a.

P2.3: Bits = bytes × 8, so 126 × 8 = 1008 (exactly twice 504, because the length header is only 16 bits and does not double along with the message); the modification count does not double — it is decided randomly by the "hit rate" between message bits and pixel LSBs: the expectation doubles, while the actual count fluctuates.

P2.4: img[:, ::2] takes every other column horizontally, making the picture thinner — but it is still a view of the original array, and modifying it changes the original.

## J.4 Chapter 3

P3.1: The pair sums stay [16, 12, 18, 14], expectations [8, 6, 9, 7], deviations [+2, 0, 0, 0], χ² = 4/8 = 0.5, df = 3, chi2_sf(0.5, 3) ≈ 0.919 — a very high p-value, with three of the four pairs completely flattened: a verdict of "suspected randomization".

P3.2: [128,128,131,131]: original f = 3; F flip → [127,127,132,132], f = 5; M flip → [129,129,130,130], f = 1. [200,201,202,203]: original f = 3; F → [199,202,201,204], f = 7; M → [201,200,203,202], f = 5. The first group is smoother under M (contributing to the Rm side); the second group gets rougher under both flips.

P3.3: Before embedding, all counts pile up at gray level 0, so the (0,1) pair gives a huge χ² and a p-value ≈ 0 (verdict "clean"); after random bits are embedded, the (0,1) pair flattens instantly and p ≈ 1 (verdict "suspicious") — the more unbalanced the background, the stronger the chi-square signal after embedding. Blind spot: embedding all-zero bits does not change a single pixel — completely traceless.

P3.4: Full-capacity embedding rewrites nearly all LSBs, the even-odd pairing is completely flattened and the bit plane completely randomized — both prob and Gn collapse to the extremes. "The more you hide, the safer" holds visually and is exactly the opposite statistically.

P3.5: The chi-square pair flattening still happens but concentrates in the mid-brightness range; the RS structural collapse weakens because "textured regions are avoided" — this is exactly the design motivation of adaptive steganography (the HUGO/S-UNIWARD family), and the SRM features of Section 8.8 were aimed straight at them.

## J.5 Chapter 4

P4.1: s = H₁⊕H₂⊕H₄⊕H₇ = [0,0,0]; d = s⊕m = [0,1,1] → H₆ → flip bit 6, codeword [1,1,0,1,0,1,1]. Error-correction drill with bit 5 wrong: s(y) = [0,1,1]⊕H₅ = [1,1,0]; if the target m were known, s(y)⊕m = [1,1,0] = H₃, locating bit 3. Note that "error correction requires knowing m or assuming s should be 0" — the stego extraction side does not know m and therefore performs no error correction; this is exactly the difference in goals between steganography and channel coding.

P4.2: For p=2 the H columns are [1,0], [0,1], [1,1], and α = 2×4/3 = 8/3. For 600 bits: p=2 needs 300 blocks × 3 bits = 900 positions, modifying 300 × 3/4 = 225 bits on average; p=3 needs 200 blocks × 7 = 1400 positions, modifying 200 × 7/8 = 175 bits on average. p=3 spends more positions to buy fewer modifications — always a good deal when capacity is to spare.

P4.3: The premise is that "cover LSBs are approximately random". With an all-zero message, m is always 0, the no-change condition becomes s = 0, and the probability is still 1/2ᵖ — the real warning is that a low-entropy message can be exploited by a "known-message attack" (an attacker who guesses the message can work backward to the embedding positions), which is why the keying of Chapter 6 matters.

P4.4: The modification count approximately doubles — the syndrome is decided jointly by "cover LSBs and the message"; when the message doubles, the block count doubles while the per-block modification probability stays the same.

P4.5: For 16 384 bits in a 512×512 image (262 144 positions), p=3 needs 5 462 blocks and p=6 needs 2 731 blocks — capacity suffices either way. Pick a large p to minimize modifications, a small p for localization granularity and robustness — the project default p=3 is the compromise point.

## J.6 Chapter 5

P5.1: For m=[0,1], d = [0,1]⊕[0,1] = [0,0]; the zero vector is not among H's columns → no modification needed. For m=[1,1], d = [1,0], and among the dry positions both position 1 and position 4 have a column that hits — the solver takes the first one in a deterministic order (the same input always yields the same plan).

P5.2: xv = [+3, 0, +1, +6, +2, +5]; wet points = position 2 (0) and position 3 (+1); flipping position 4: 134 → 133 (+6 → +5, a legal decrement).

P5.3: The wet/dry split constrains "where changes are allowed" **only on the embedding side**; the extraction side simply reads the LSBs of all carriers in the same order (after a dry point is flipped, |c| is still ≥1, so it never disappears from the carrier set). If the wet points were instead decided by a passphrase-driven pseudorandom sequence, the embedding would modify positions outside the wet set it itself drew — the extraction side could no longer know "which bits are trustworthy", and self-synchronization would fail. The beauty of content derivation is exactly this: the embedding touches only dry points; after dry flips the image content has changed, but "which positions were flipped" is verified by the extraction side from the message itself — no need to recompute the wet points.

P5.4: On smooth images (such as the gradient demo) a large share of pixels fall on 127/128/129, so the wet-point density is high — nsF5 steers around them while matrix embedding pays no attention; the latter keeps hitting mines and retrying, and its modification count ends up higher. Conclusion: algorithm comparisons must fix the test image — "which is better" is relative to the image statistics.

P5.5: When every carrier is a wet point, the dry set is empty and the equations generally have no solution — the project raises CapacityError (compare the 16×16 all-128 case of test_capacity_error), hinting to switch to a larger image / higher quality / shorter message.

## J.7 Chapter 6

P6.1: After the first state advance, x = 9e3779b97f4a7c15 (the golden constant itself), and the output is 16 294 208 416 658 607 535.

P6.2: There are three sticking points — ① the header pool needs seed0 (derived from the passphrase), and with a wrong passphrase the "hash" read out is garbage; ② the seedB derived from the garbage hash shuffles the body pool into a completely different order; ③ even if the bits happen to read back, the length header and the content-hash check both fail. Given a second image with the same passphrase, an attacker can compare whether the two images' header-pool positions coincide (the same seed0) — this is why "multiple images, one passphrase" requires rotating the master key.

P6.3: In a teaching project the attacker model is "an ordinary opponent who has the images and the source code", and a content hash is enough to make a wrong passphrase and image tampering fail reliably; a real forensic product faces strong attackers who can re-embed an entire image, and must use a keyed MAC to restrict "who can compute a valid hash" to key holders.

P6.4: It would succeed — re-saving as PNG leaves the pixels unchanged, so the LSBs and header bits are fully intact. The reason hash awareness is not triggered: in the pixel domain the anchor is the byte hash of the **original cover**, with the semantics "repro/experiment archives compare against the original image", not "compare against the stego image"; the JPEG domain has a more ingenious design — the anchor is the chroma hash, the embedding touches only luma Y, and as long as the chroma is unchanged the check passes. Understand the layers, and each sits where it belongs.

P6.5: Measured, about 47%–53% of bit flips (e.g., 121/256 in Section 6.4) — averaged over many runs it lands very close to 128/256.

## J.8 Chapter 7

P7.1: η=10: w = 0 − 10×(−0.1) = 1.0, new loss about 0.349 (still falling); η=100: w = 10, the clean sample's prediction is pushed close to 1, and the loss rises to about 1.54 — the step is too large, and one stride jumps across the valley floor. The larger the feature scale, the more dangerous the same learning rate becomes.

P7.2: Grouping by the pseudo photo_id (same-source samples in the same fold) is the sounder choice — otherwise "sibling samples" appear on both the training and validation sides, inflating the validation score.

P7.3: The false positive (FP) — judging a clean image as stego. In a forensic setting that means casting suspicion on the innocent, a social cost higher than missing one weakly embedded image.

P7.4: sklearn's LogisticRegression applies regularization and a different optimizer by default; the direction should match the hand calculation (w positive) while the numbers need not — exactly the chance to feel the difference of "one model, different solvers".

P7.5: The mistake is comparing scores across different corpora (RESULTS.md: numbers from different corpora are not comparable) — 0.89 vs 0.81 reflects corpus difficulty, not model strength.

## J.9 Chapter 8

P8.1: Ranked by how much domain knowledge is built in: yenet (fixed SRM kernel front-end) > 143d (SRM statistical features) > 53d/11d (handcrafted statistics) > xuNet (no domain knowledge). The AUC ranking agrees roughly (0.9541 > 0.8062 > 0.7172 ≈ 0.7128 > 0.5007) — but 143d trailing yenet reminds us that beyond "putting knowledge in the right place", the expressive power of the end-to-end architecture is also a variable; the two are not two knobs on the same machine.

P8.2: A perfect model's ROC is the "bent line hugging the top-left corner": a 0% false-positive rate at 100% detection, AUC = 1.0; a random model's ROC is the diagonal, AUC = 0.5.

P8.3: Sources of the difference: your photo style (content complexity), the shooting device (noise floor), whether the grouping is strict, the sample size — any one of them is enough to push the AUC away from the README.

P8.4: The symmetric problem appears — the model takes PNG's characteristic "uncompressed noise" as an anomaly, creating new false-positive/false-negative shifts for a real JPEG deployment scenario. Aligning the training distribution with the deployment distribution is a higher priority than tuning hyperparameters.

P8.5: 53d is the mandatory pick for explaining the decision basis to non-technical audiences/reviewers and for compliance scenarios that need to audit what each dimension means; 143d is the mandatory pick for bulk screening in online services (accuracy first) and as a research baseline against strong embedding variants.

## J.10 Chapter 9

P9.1: The expected top three are the deterministic permutation, the inner loops of the feature statistics, and file IO — the first two are the targets Section 9.2 sinks down, and the third can be optimized with buffered reading and writing.

P9.2: Fix the seeds and inputs → call the two versions of the permutation → diff bit by bit (np.array_equal) → repeat over several seeds and sizes, and pass only when everything agrees.

P9.3: This project's positioning includes "usable without acceleration" (servers / CI / teaching machines), and the fallback guarantees identical functionality and results; if performance were a hard requirement (say, an online service), the degradation should instead be "a clear error + require installation", avoiding a silent slowdown.

P9.4: Changing algorithm parameters first trips the unit layer (the round-trip assertions in test_core); a file missing from the package first trips the system layer (items 4/5 of the frozen-build smoke test).

## J.11 Chapter 10

P10.1: An example of a good point of suspicion — "Of the gain of 143d over 11d, how much comes from SRM and how much from the data expansion?" Reproduction steps: fix the photo grouping and train 11d and 143d separately; acceptance criterion: under the same protocol, an AUC gap ≥0.02 with non-overlapping confidence intervals.

P10.2: The hypothesis must be falsifiable ("the new feature improves AUC by ≥0.02"), the protocol must group by source image, and the acceptance criterion goes into the experiment script.

P10.3: When replaying the recording, listen above all for: whether the corpus and protocol behind the numbers were stated clearly, and whether "correlation" was passed off as "causation".

## J.12 Chapter 11

P11.1: The key to judging the statements is citing technical facts — for example, the point of ② is "steganography's concealment was used to deceive a specific audience", not "steganography is a bad technology".

P11.2: An example upgrade plan (hash keying → HMAC): the passphrase derives an HMAC key via PBKDF2; all key fields of the header and body switch to HMAC coverage; acceptance = all existing round-trip tests green + new "tampered fields must fail" cases.

P11.3: Example locations — the α formula in the README and the implementation in efficiency.py; the 0.8062 in RESULTS.md and the evaluation output of train_model.py; the GUI's 0.2% hint and the statistics report of _embed.
