# 附录 D · 概念 → 代码定位表

学习后期“忘了某概念在哪个文件”，查这张表最快。

| **概念** | **文件** | **优先阅读内容** |
| --- | --- | --- |
| 消息编码/长度头 | src/ns5_core.py | encode_string / decode_string |
| 图像哈希/种子 | src/ns5_core.py | derive_seed / get_image_hash |
| 确定性置换 | src/ns5_core.py | permute_index |
| 汉明码/伴随式 | src/ns5_core.py | build_hamming / syndrome |
| 矩阵嵌入 | src/ns5_core.py | MatrixEmbedding._embed |
| 湿纸求解 | src/ns5_core.py | solve_wet_paper / gauss_solve_GF2 |
| 像素域 nsF5 | src/ns5_core.py | nsF5Pixel._embed |
| 高层嵌入/解码 | src/ns5_core.py | embed_string / extract_string |
| 卡方统计 | src/steganalysis.py | chi2_stats / chi2_sf |
| RS 统计 | src/steganalysis.py | rs_metrics |
| 综合判读 | src/steganalysis.py | analyze |
| 特征顺序 | src/fsfeatures.py / ml_predict.py | FEAT_KEYS |
| 训练流水线 | src/train_model.py | main() |
| 数据集生成 | src/make_dataset.py | main() |
| C++ 嵌入封装 | src/cppembed.py | embed_string / selfcheck |
| GPU 特征 | gpu/featurize_gpu.py | 批量算子与 check_vs_cpu |
| GUI 回调 | src/gui.py | 按钮事件 → 核心函数 |
| v2 特征计算 | src/featurize_v2.py | ALL_FEATURE_NAMES / featurize_v2() |
| SRM 预处理 | src/srm_filter.py | srm_residuals_np / preprocess_batch_torch |
| 模型推理（双版本） | src/ml_predict.py | MLPredictor(model_path=…, clip_outliers=…) |
| GPU v2 特征 | gpu/featurize_v2_gpu.py | extract_features_v2_gpu() 与自检 |
