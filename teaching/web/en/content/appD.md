# Appendix D - Concept-to-Code Map

<!-- lang-switch -->
> [🌐 中文版](https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/appD.html)




| **Concept** | **File** | **Read first** |
| --- | --- | --- |
| Message encoding / length header | src/ns5_core.py | encode_string / decode_string |
| Image hash / seeds | src/ns5_core.py | derive_seed / get_image_hash |
| Deterministic permutation | src/ns5_core.py | permute_index |
| Hamming code / syndrome | src/ns5_core.py | build_hamming / syndrome |
| Matrix embedding | src/ns5_core.py | MatrixEmbedding._embed |
| Wet paper solver | src/ns5_core.py | solve_wet_paper / gauss_solve_GF2 |
| Pixel-domain nsF5 | src/ns5_core.py | nsF5Pixel._embed |
| High-level embed/extract | src/ns5_core.py | embed_string / extract_string |
| Chi-square statistics | src/steganalysis.py | chi2_stats / chi2_sf |
| RS statistics | src/steganalysis.py | rs_metrics |
| Combined verdict | src/steganalysis.py | analyze |
| v1 feature order | src/fsfeatures.py / ml_predict.py | FEAT_KEYS / V1_FEAT_KEYS |
| v2 143-D features | src/featurize_v2.py | ALL_FEATURE_NAMES / featurize_v2() |
| SRM preprocessing | src/srm_filter.py | srm_residuals_np / preprocess_batch_torch |
| Training pipeline | src/train_model.py | main() |
| Dataset generation | src/make_dataset.py | main() |
| C++ embedding wrapper | src/cppembed.py | embed_string / selfcheck |
| Dual-model inference | src/ml_predict.py | MLPredictor(model_path=..., clip_outliers=...) |
| GPU v1 features | gpu/featurize_gpu.py | batch operators / check_vs_cpu |
| GPU v2 features | gpu/featurize_v2_gpu.py | extract_features_v2_gpu() / self-check |
| GUI callbacks | src/gui.py | button events -> core functions |
