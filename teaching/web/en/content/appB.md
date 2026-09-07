# Appendix B - Command Cheat Sheet

<!-- lang-switch -->
> [🌐 中文版](../../zh/content/appB.md)


Run from the project root F:\Steganography.

| **Purpose** | **Command** |
| --- | --- |
| Install core dependencies | pip install numpy pillow |
| Install everything (ML/plot) | pip install -e . |
| Core algorithm self-test | python src\test_core.py |
| Steganalysis self-test | python src\test_steg.py |
| False-positive regression | python src\test_false_positive.py |
| GUI smoke test | python src\test_gui.py |
| End-to-end verification | python src\run_e2e.py |
| Launch the GUI | python src\gui.py |
| Code-family/efficiency plot | python -c "import sys; sys.path.insert(0,'src'); from efficiency import plot_code_family_and_efficiency; print(plot_code_family_and_efficiency())" |
| Generate v1 dataset | python src\make_dataset.py data\campus_jpg --out campus |
| Generate v2 dataset (12 variants / 143-D) | python src\make_dataset.py --out campus_v2 --feature-set v2 --variants all |
| Generate SRM-enhanced dataset (same source) | python src\make_dataset.py data\campus_jpg --out campus_srm --preprocess srm -j 16 |
| Train/evaluate a dataset | $env:DS_FILES = "dataset.csv"; python src\train_model.py |
| Train on v2 + JPEG clean | $env:DS_FILES = "dataset_campus_v2_jpeg.csv"; python src\train_model.py |
| Single-image ML prediction | python -c "import sys; sys.path.insert(0,'src'); from ml_predict import get_predictor; import numpy as np; from PIL import Image; print(get_predictor().predict(np.asarray(Image.open('img/cover.png').convert('L'))))" |
| Switch to 53d interpretable model | python -c "import sys; sys.path.insert(0,'src'); from ml_predict import MLPredictor; import numpy as np; from PIL import Image; print(MLPredictor(model_path='models/stego_classifier_v2_jpeg_lgb_51d.joblib', clip_outliers=False).predict(np.asarray(Image.open('img/cover.png').convert('L'))))" |
| C++/Python consistency check | python -c "import sys; sys.path.insert(0,'src'); import cppembed; cppembed.selfcheck()" |
| GPU dataset generation | python gpu\make_imageset.py |
| GPU feature self-check | python gpu\featurize_gpu.py |
| GPU v2 feature self-check | python gpu\featurize_v2_gpu.py |
| GPU training | python gpu\train_ml_gpu.py |
| GPU single-image detection | python gpu\predict_gpu.py img\cover.png |
| BOSSbase multi-source (GPU) | python gpu\make_imageset.py data\BOSSbase_1.01 --out bossbase, then python gpu\train_ml_gpu.py |
| Build packages | python -m build |
| Install wheel | pip install dist\nsf5stego-1.4.0-py3-none-any.whl |
