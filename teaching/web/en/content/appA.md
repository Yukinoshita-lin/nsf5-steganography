# Appendix A - Glossary

<!-- lang-switch -->
> [🌐 中文版](../../zh/content/appA.md)


Arranged roughly in reading order. Mastering the bold-faced terms covers almost everything in this handbook.

| **Term** | **Also known as** | **One-line meaning** |
| --- | --- | --- |
| Steganography | - | Hiding a secret inside an innocent carrier so the act of communication is hidden |
| Steganalysis | - | Deciding whether a carrier hides a secret, from statistics or learning |
| cover / stego | carrier / embedded image | Original image / image after embedding |
| LSB | least significant bit | Lowest bit of a pixel; flipping it is visually negligible |
| bit plane | - | Binary layer formed by one bit position across all pixels |
| redundancy | - | Carrier parts that can be modified without obvious artifacts |
| capacity / payload | embedding capacity | Maximum secret bits an image can carry |
| relative payload | - | Embedded bits divided by available positions |
| embedding efficiency | alpha | Average secret bits per modification, alpha |
| matrix embedding | - | Group coding that embeds p bits while changing at most one position |
| Hamming code | binary Hamming code | Linear error-locating code with block [n,k,3] |
| parity-check matrix | H matrix | p x n matrix with distinct columns used to compute syndromes |
| syndrome | - | s = H*x (mod 2); a summary of the block state |
| GF(2) | Galois field of two elements | Field containing only 0/1 with XOR arithmetic |
| shrinkage | - | Coefficient magnitude decrease lands on zero, ruining the block |
| wet paper coding | WPC | Embedding on dry positions while wet positions stay untouched |
| dry / wet positions | - | Modifiable positions / untouchable positions |
| F5 / nsF5 | - | JPEG matrix-embedding algorithm; nsF5 removes shrinkage with wet paper |
| magnitude decrease | coefficient shrink | Reducing \|coefficient\| by 1 to flip LSB parity |
| SHA-256 | - | 256-bit cryptographic hash used for image keying |
| keying | - | Using password/content keys to decide hiding positions |
| deterministic permutation | - | Shuffle where the same seed always gives the same order |
| splitmix64 | - | 64-bit PRNG used by the project |
| Fisher-Yates | - | Standard uniform shuffle algorithm |
| self-synchronization | - | Decoder finds the payload without external parameters |
| tamper perception | - | Detecting that an image was modified |
| blind steganalysis | - | Statistical detection without the original cover |
| chi-square test | Westfeld test | Checks whether gray-level pairs were balanced |
| p-value | - | Probability that observations fit the assumption; here high p is suspicious |
| RS analysis | - | Counts regular/singular groups under +/- masks |
| regular / singular | R / S groups | Groups whose discriminant rises / falls after flipping |
| difference entropy | - | Shannon entropy of adjacent differences; measures texture randomness |
| Shannon entropy | - | Information/uncertainty measure in bits |
| supervised learning | - | Training a model on labeled samples |
| feature vector | - | Numeric description of a sample (11-D v1 or 143-D v2 here) |
| label | - | Ground truth (0 = clean, 1 = stego) |
| binary classification | - | Predicting membership of one of two classes |
| logistic regression | - | Linear combination + sigmoid; an interpretable classifier |
| sigmoid | - | S-shaped function mapping any real number to 0-1 |
| cross-entropy loss | - | Standard classification loss |
| gradient descent | - | Iteratively moving parameters downhill in loss |
| overfitting | - | Memorizing training data at the cost of generalization |
| cross-validation | - | Rotating validation folds to estimate generalization |
| data leakage | - | Validation information entering training, inflating metrics |
| GroupKFold | - | Grouped cross-validation (same photo's samples stay together) |
| confusion matrix | - | Four-cell counts of truth vs prediction |
| precision / recall | - | Share of flagged that are real / share of real that are caught |
| ROC / AUC | - | Detection-vs-FP curve across thresholds and its area |
| Youden's J | - | Threshold maximizing TPR - FPR |
| false positive / negative | FP / FN | Clean flagged as stego / stego missed |
| SRM | Spatial Rich Model | High-pass residual filter family that highlights embedding noise |
| residual map | - | Noise residual after high-pass filtering |
| LightGBM / LGB | - | Gradient-boosting implementation used by the v1.4 models |
| feature group | - | A batch of features from one source (BASE/SRM/PREFIX/LSB-PREFIX) |
| out-of-distribution | OOD | Inputs unlike the training distribution (e.g., real JPEG clean) |
| BOSSbase | BOSSbase 1.01 | Standard benchmark: 10,000 512x512 grayscale PGM images |
| PGM | - | Lossless grayscale image format (BOSSbase carrier format) |
| stacking | meta-learner | Ensemble where a second model combines base-model predictions |
| memmap | memory-mapped file | Large arrays written/read in slices to avoid OOM |
| calibration set | - | Separate subset used only for threshold selection |
| grid tuning | - | Searching a hyperparameter grid and comparing models |
| dual-version model | - | 143d robust model + 53d interpretable model deployed together |
| ctypes | - | Python binding mechanism for C/C++ DLLs |
| DLL | dynamic-link library | Windows shared library |
| CUDA / batching | - | GPU parallelism / processing many samples at once |
| consistency check | - | Bit-level comparison between C++/GPU and Python outputs |
