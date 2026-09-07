# 附录 B · 常用命令速查

<!-- lang-switch -->
> [🌐 English version](https://yukinoshita-lin.github.io/nsf5-steganography/en/content/appB.html)




以下命令均在项目根目录 F:\Steganography 下执行。

| **目的** | **命令** |
| --- | --- |
| 安装核心依赖 | pip install numpy pillow |
| 安装全部依赖（ML/绘图） | pip install -e . 或 pip install numpy pillow matplotlib scikit-learn joblib pandas |
| 核心算法自测 | python src\test_core.py |
| 隐写分析自测 | python src\test_steg.py |
| 误报回归测试 | python src\test_false_positive.py |
| GUI 冒烟测试 | python src\test_gui.py |
| 端到端验证 | python src\run_e2e.py |
| 启动图形界面 | python src\gui.py |
| 生成码族/效率图 | python -c "import sys; sys.path.insert(0,'src'); from efficiency import plot_code_family_and_efficiency; print(plot_code_family_and_efficiency())" |
| 生成特征数据集 | python src\make_dataset.py data\campus_jpg --out campus |
| 训练/评估分类器 | $env:DS_FILES = "dataset.csv"; python src\train_model.py |
| 单图 ML 判定 | python -c "import sys; sys.path.insert(0,'src'); from ml_predict import get_predictor; import numpy as np; from PIL import Image; print(get_predictor().predict(np.asarray(Image.open('img/cover.png').convert('L'))))" |
| C++/Python 一致性自检 | python -c "import sys; sys.path.insert(0,'src'); import cppembed; cppembed.selfcheck()" |
| GPU 数据集生成 | python gpu\make_imageset.py |
| GPU 特征自检 | python gpu\featurize_gpu.py |
| GPU 训练 | python gpu\train_ml_gpu.py |
| GPU 单图检测 | python gpu\predict_gpu.py img\cover.png |
| 构建发布包 | python -m build |
| 安装 wheel | pip install dist\nsf5stego-1.4.0-py3-none-any.whl |
| 生成 v2 数据集（12 档 / 143 维） | python src\make_dataset.py --out campus_v2 --feature-set v2 --variants all |
| 生成 SRM 增强数据集（同源） | python src\make_dataset.py data\campus_jpg --out campus_srm --preprocess srm -j 16 |
| 指定 v2+JPEG 数据集训练 | $env:DS_FILES = "dataset_campus_v2_jpeg.csv"; python src\train_model.py |
| GPU v2 特征自检 | python gpu\featurize_v2_gpu.py |
| BOSSbase 多源生成 + GPU 训练 | py gpu\make_imageset.py data\BOSSbase_1.01 --out bossbase（再运行 python gpu\train_ml_gpu.py） |
| 切换 53d 可解释模型（API） | python -c "import sys; sys.path.insert(0,'src'); from ml_predict import MLPredictor; import numpy as np; from PIL import Image; print(MLPredictor(model_path='models/stego_classifier_v2_jpeg_lgb_51d.joblib', clip_outliers=False).predict(np.asarray(Image.open('img/cover.png').convert('L'))))" |
