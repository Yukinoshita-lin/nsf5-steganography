"""
有监督 ML 隐写判定 —— 对单张图像给出"含密概率"。

- 预处理与训练一致: 转灰度 → LANCZOS 缩放到 512x512
- 特征: 11 维 (v1, C++ fsfeatures.dll) 或 143 维 (v2, src/featurize_v2.py) — 由模型 features 列数自动识别
- 模型: models/stego_classifier.joblib (训练自校园照片 clean/stego 数据集)
- 阈值: 默认用 Youden 平衡点; 可用 low_fp 档(低误报但检出极弱)
- 部署抗分布偏移: v2 模型可选 `clip_outliers=True` —— 把每个特征 clip 到
  `train_mu ± 5σ` 范围(从数据集 CSV 加载训练统计); 缓解真实 JPEG 干净图在
  v2 SRM 残差上偏出训练分布导致的过激判读(原 prob=1.0 -> clip 后 0.7~0.9)。

说明: 对真 JPEG 照片, LSB 位平面天然近乎随机, 弱密度 nsF5 嵌入的
统计足印很弱, ML 概率只是辅助判读, 与启发式(S)交叉印证。
"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(PROJ, "models", "stego_classifier.joblib")
TRAIN_CSV = os.path.join(PROJ, "data", "dataset.csv")  # v1 训练集 (基线)

V1_FEAT_KEYS = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
                "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
                "median_prefix_p", "chi2_stat"]
WORK_SIZE = (512, 512)


class MLPredictor:
    def __init__(self, model_path: str = MODEL_PATH, sensitivity: str = "均衡",
                 clip_outliers: bool = False, n_sigma: float = 5.0):
        try:
            from joblib import load
            pkg = load(model_path)
        except Exception:
            pkg = None
        self._pkg = pkg
        self.sensitivity = sensitivity
        self.clip_outliers = clip_outliers
        self.n_sigma = n_sigma
        self._clip_stats = None
        if clip_outliers and pkg is not None and len(pkg.get("features", [])) > 11:
            self._clip_stats = self._load_clip_stats(pkg["features"])

    def _load_clip_stats(self, feats):
        """从训练集 CSV 加载每列 mean / std, 用于部署时 clip."""
        import pandas as pd
        # 优先用 v2 训练集; 找不到时退回 v1
        candidates = [
            os.path.join(PROJ, "data", "dataset_campus_v2.csv"),
            os.path.join(PROJ, "data", "dataset.csv"),
        ]
        for p in candidates:
            if not os.path.exists(p):
                continue
            try:
                df = pd.read_csv(p)
            except Exception:
                continue
            avail = [c for c in feats if c in df.columns]
            if len(avail) < len(feats) * 0.9:
                continue
            X = df[feats].values.astype(np.float64)
            mu = X.mean(0)
            sigma = X.std(0).clip(min=1e-9)
            return (mu - self.n_sigma * sigma, mu + self.n_sigma * sigma)
        return None

    @property
    def available(self) -> bool:
        return self._pkg is not None

    def _threshold(self) -> float | None:
        """按灵敏度选择判定阈值: 严格→低误报点; 宽松→均衡阈值下探以提高检出。"""
        if not self.available:
            return None
        d = self._pkg
        if self.sensitivity.startswith("严格"):
            return float(d.get("threshold_low_fp", d["threshold"]))
        if self.sensitivity.startswith("宽松"):
            return max(0.05, float(d["threshold"]) * 0.75)
        return float(d["threshold"])

    @staticmethod
    def preprocess(image: np.ndarray) -> np.ndarray:
        img = np.ascontiguousarray(image)
        if img.ndim == 3:
            img = img[..., 0]
        a = Image.fromarray(img)
        if a.size != WORK_SIZE:
            a = a.resize(WORK_SIZE, Image.LANCZOS)
        return np.asarray(a, dtype=np.uint8)

    def predict(self, image: np.ndarray) -> dict:
        """返回 {probability, verdict, threshold}。模型缺失时 available=False。"""
        if not self.available:
            return {"probability": None, "verdict": "ML 模型未加载", "threshold": None}
        a = self.preprocess(image)
        # 自动按模型 features 列数选择特征集
        feats_model = self._pkg.get("features", V1_FEAT_KEYS)
        if len(feats_model) == 11:
            try:
                from fsfeatures import get_lib
                feats = get_lib().features(a)
            except Exception:
                from py_features import features as py_features_fn
                feats = py_features_fn(a)
            x = np.array([feats[k] for k in V1_FEAT_KEYS], dtype=np.float64).reshape(1, -1)
        elif len(feats_model) == 143:
            from featurize_v2 import featurize_v2
            x = featurize_v2(a).reshape(1, -1)
        else:
            return {"probability": None, "verdict": f"模型特征数 {len(feats_model)} 暂不支持", "threshold": None}
        if self.clip_outliers and self._clip_stats is not None and len(feats_model) > 11:
            lo, hi = self._clip_stats
            x = np.clip(x, lo, hi)
        # STACK 模型需要先用 base_models 取概率, 再喂给 stacker
        model_name = self._pkg.get("name", "")
        if model_name == "STACK" and self._pkg.get("base_models") and self._pkg.get("stacker") is not None:
            base_probs = np.array([[float(clf.predict_proba(x)[0, 1])
                                    for clf in self._pkg["base_models"].values()]])
            p = float(self._pkg["stacker"].predict_proba(base_probs)[0, 1])
        else:
            p = float(self._pkg["model"].predict_proba(x)[0, 1])
        thr = self._threshold()
        verdict = ("判定为含密 (ML)" if p >= thr else
                   "判定为干净 (ML)" if p < thr * 0.9 else "ML: 边界不清")
        return {"probability": p, "verdict": verdict, "threshold": thr}


_predictor = None
def get_predictor(sensitivity: str = "均衡", clip_outliers: bool = False,
                  n_sigma: float = 5.0) -> MLPredictor:
    global _predictor
    if (_predictor is None
            or _predictor.sensitivity != sensitivity
            or _predictor.clip_outliers != clip_outliers
            or _predictor.n_sigma != n_sigma):
        _predictor = MLPredictor(sensitivity=sensitivity, clip_outliers=clip_outliers,
                                 n_sigma=n_sigma)
    return _predictor


if __name__ == "__main__":
    import numpy as np
    p = get_predictor()
    print("模型可用:", p.available, "路径:", MODEL_PATH)
    if p.available:
        img = np.random.default_rng(0).integers(0, 256, (256, 256), dtype=np.uint8)
        print("随机图(应为干净)概率:", p.predict(img)["probability"])
