# Appendix G · Exercises and Self-Test (with Answer Keys)

<!-- lang-switch -->
> [🌐 中文版](https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/appG.html)

This appendix gathers the most important takeaways into a set of self-test questions,
covering "steganography vs encryption / LSB & statistical fingerprints / matrix embedding /
nsF5 & wet paper / hash keying / ML evaluation". Answer them yourself first, then compare
with the key; each question notes the relevant chapter, so revisit that chapter if you get stuck.

> **How to use |** Read the question, write or compute your answer first, then read the
> explanation. The code snippets below all run in the project.

## G.1 Steganography vs Encryption (Ch. 3)

**Q1** In one sentence, what do "encryption" and "steganography" protect respectively, and why is "encrypt first, then hide" recommended?

<details>
<summary>Answer</summary>

- **Encryption** protects the *content*: without the key you cannot read the plaintext.
- **Steganography** protects the *existence*: nobody can tell there is a secret.
- Encrypt first, then hide: the ciphertext looks like random bits, so it is less likely to
  stand out statistically. The two are usually combined (see 3.1).
</details>

**Q2** True or false, and why: "LSB steganography exploits visual redundancy but breaks statistical redundancy."

<details>
<summary>Answer</summary>

True. The eye cannot notice a 1-level gray difference (visual redundancy), so changing the LSB is
invisible; but LSB replacement flattens the even/odd counts of adjacent gray pairs and destroys the
spatial structure of the LSB plane (statistical redundancy). That is exactly the fingerprint the
chi-square test and RS analysis catch (see 3.3, 3.4).
</details>

## G.2 LSB and Statistical Fingerprints (Ch. 3)

**Q3** After LSB replacement, what happens to the chi-square **p-value**? Why? Does "high p" mean safe?

<details>
<summary>Answer</summary>

- LSB replacement forces the even/odd counts of adjacent pairs (2i, 2i+1) toward balance, so the
  chi-square statistic drops and the **p-value rises**.
- **Not necessarily safe**: a naturally noisy photo already has a near-random LSB and a high p.
  So the project adds a "content background randomness" correction (gray difference entropy) to judge
  how random the image is before treating a high p as embedding evidence (see the tip at the end of 3.3).
</details>

**Q4** In RS analysis, what does $G_n$ tend toward for a clean image vs an embedded one, and why?

<details>
<summary>Answer</summary>

A clean natural image has structured LSBs; applying the negative mask turns many groups from "regular" to
"singular", so $G_n=(R_n-S_n)/n$ is clearly positive (commonly 0.3~0.7 for clean smooth images). LSB
randomization collapses that structure, positive/negative masks behave alike, and $G_n$ approaches 0 (see 3.4).
</details>

## G.3 Matrix Embedding (Ch. 4)

**Q5** For p=3, how many bits can be hidden and what is the block length? Explain why flipping one column achieves the target syndrome.

<details>
<summary>Answer</summary>

For p=3 the block length is $n=2^p-1=7$ and it hides $p=3$ bits. Compute the syndrome of the current LSB
block $s=Hx$, XOR with the target message $m$ to get the difference $d=s\oplus m$. Each column of $H$ is a
3-bit binary number; if $d$ equals one column (or the XOR of a few columns), flipping that column's pixel
makes $Hx'=m$. Usually only one pixel needs flipping (see 4.1, 4.2).
</details>

**Q6** Why does matrix embedding hide more and change fewer pixels than naive LSB?

<details>
<summary>Answer</summary>

Naive LSB hides 1 bit per pixel and changes 1 pixel. Matrix embedding spreads p message bits over an
$n=2^p-1$-pixel LSB block and only expects to flip about $1-2^{-p}$ pixels. So the "bits carried per change"
(embedding efficiency) rises sharply with p (see the efficiency figure 4-2).
</details>

## G.4 nsF5 and Wet Paper (Ch. 5)

**Q7** How are "wet/dry" points defined in nsF5? Why does marking wet points first avoid shrinkage?

<details>
<summary>Answer</summary>

Let $xv=$ pixel $-128$. A **wet point** has $|xv|\le1$ (pixels 127/128/129) - decrementing it can hit an
illegal value/zero; a **dry point** has $|xv|>1$ (see 5.1). Embedding only solves on dry points (wet paper
coding), so it never "hits zero halfway", every block embeds successfully, no retry, and no extra zero
coefficients - hence **no shrinkage** (see 5.2, 5.3).
</details>

**Q8** What is the mathematical essence of "wet paper coding cannot find a solution"?

<details>
<summary>Answer</summary>

We must solve $Hy=d$ using only dry columns. The dimension of the space spanned by the dry columns equals the
rank $r$ of the dry-column matrix; when $r<p$ (not enough dry points), some $d$ lie outside that subspace and is
unsolvable (see 5.6). That is the mathematical essence of "not enough dry points".
</details>

## G.5 Hash Keying (Ch. 6)

**Q9** What does image hash keying solve, and what is its limitation?

<details>
<summary>Answer</summary>

Embedding positions are derived from the password and permuted (`permute_index`, splitmix64 + Fisher-Yates), so:
- It solves: the decoder does not need to record where each block is; it can re-derive positions from the password
  ("self-synchronization", see 6.2).
- Limitation: crypto strength depends on the password; a weak/leaked password makes positions predictable. Hash
  keying gives *unpredictable positions*, not "invisibility" (see the reading notes of Ch. 6).
</details>

## G.6 Machine Learning Evaluation (Ch. 7-8)

**Q10** Why must data be split by `photo_id` (GroupKFold) instead of a random KFold?

<details>
<summary>Answer</summary>

Variants of the same photo are highly similar; a random split puts "siblings" on both sides of train/test,
causing **data leakage** and inflated scores. GroupKFold keeps all variants of a photo in the same fold, so the
OOF score is honest (see 7.6, 7.7).
</details>

**Q11** Under class imbalance, why is "accuracy" misleading? Which metrics should you look at?

<details>
<summary>Answer</summary>

If there are far more stego than clean samples, a model that labels everything "stego" achieves high accuracy
while false-positiving every clean image. Look at AUC (ranking ability, threshold-independent), precision/recall,
and F1 instead (see 7.7.3, 8.5).
</details>

**Q12** What does AUC=0.7 roughly mean, and why must you still pick a threshold for deployment?

<details>
<summary>Answer</summary>

AUC=0.7 means: draw one stego and one clean image at random, and the model ranks the stego higher about 70% of the
time - usually right, but not great (weak densities are hard; see 7.7.1). AUC is threshold-independent, but
deployment needs one threshold: higher -> conservative (fewer false positives, more misses), lower -> aggressive
(more detection, more false positives); it is a trade-off between false positives and misses (see 7.7.2, 8.6).
</details>

## G.7 Capstone (Ch. 10)

**Q13** Design a minimal honest experiment to show your new feature actually helps, and name the consistency rules you must keep.

<details>
<summary>Answer</summary>

Use `make_dataset.py` to build clean/stego variants of the same photos -> extract features (baseline vs your new
feature) -> compare AUC with the **same test-photo groups + 5-fold GroupKFold OOF** -> evaluate the held-out test
set exactly once. Key rules: separate train/calibrate/test; split a calibration set out of the training pool to pick
the threshold; evaluate the test set only once (otherwise it becomes "dirty"). See 8.8 and the honest-evaluation
pipeline of Ch. 10 (Fig. 10-1).
</details>

> **Grade yourself |** If you can answer all 13 with examples, you can already explain this body of knowledge to
> someone else. For any you missed, go back to that chapter and read it again with the "Think about it / Try it"
> blocks. Once you pass all of them, return to the intro's Section 0.4 and hand yourself a "certificate of completion".
