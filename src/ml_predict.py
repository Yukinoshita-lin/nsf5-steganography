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
        # 加载失败的原因必须留下来。此前是一个光秃秃的 `except Exception:
        # pkg = None`, 于是"模型没打进 wheel / 文件缺失 / 依赖不匹配"三种完全
        # 不同的问题在用户眼里都只是 available=False, 既无法自查也让 CI 里那次
        # 镜像构建失败只显示"模型未能加载"而无从下手。
        self._load_error = None
        try:
            from joblib import load
            pkg = load(model_path)
        except Exception as exc:  # noqa: BLE001 - 记录下来交给调用方展示
            pkg = None
            self._load_error = f"{type(exc).__name__}: {exc}"
        self._pkg = pkg
        self.model_path = model_path
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

    @property
    def load_error(self) -> str | None:
        """模型加载失败的原因 (成功时为 None)。用于把 available=False 从
        一句无信息量的提示变成可排查的错误。"""
        return self._load_error

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
        """与**训练语料**一致的预处理: 转灰度(亮度) → 512×512 LANCZOS。

        2026-09-15 修正: 这里原来对彩色图取 `img[..., 0]` (第一个通道, RGB 时即红
        通道), 而语料是 `make_dataset.py` 用 `.convert("L")` (亮度) 建的 —— 彩色
        输入因此存在训练/推理偏差。实测在 30 张真实照片上平均概率差 0.24、最大
        0.97, OOD 误报率从 9.58% 变成 29.71%。现在统一走亮度转换。
        (灰度输入两者等价, 所以 GUI 与既有灰度用法不受影响。)
        """
        img = np.ascontiguousarray(image)
        a = Image.fromarray(img)
        if a.mode != "L":
            a = a.convert("L")
        if a.size != WORK_SIZE:
            a = a.resize(WORK_SIZE, Image.LANCZOS)
        return np.asarray(a, dtype=np.uint8)

    def predict(self, image: np.ndarray) -> dict:
        """返回 {probability, verdict, threshold}。模型缺失时 available=False。"""
        if not self.available:
            return {"probability": None, "verdict": "ML 模型未加载", "threshold": None}
        a = self.preprocess(image)
        feats_model = self._pkg.get("features", V1_FEAT_KEYS)
        if len(feats_model) == 11:
            try:
                from fsfeatures import get_lib
                feats = get_lib().features(a)
            except Exception:
                from py_features import features as py_features_fn
                feats = py_features_fn(a)
            x = np.array([feats[k] for k in V1_FEAT_KEYS], dtype=np.float64).reshape(1, -1)
            return self._score(x)
        if len(feats_model) in (143, 53):
            from featurize_v2 import featurize_v2
            return self.predict_from_v2(featurize_v2(a).reshape(1, -1))
        return {"probability": None, "verdict": f"模型特征数 {len(feats_model)} 暂不支持",
                "threshold": None}

    def predict_from_v2(self, x143: np.ndarray) -> dict:
        """用**已算好的 143 维 v2 特征**打分。

        与 `predict()` 共用同一条打分路径 (特征裁剪 → 模型 → 阈值 → 判词), 区别只是
        特征由调用方提供。用途: 一张图要喂给多个模型时 (例如 OOD 评估里 143d 与 53d
        都要打分), 143 维特征只需算一次 —— 53d 本身就是 143d 的子集, 重复计算纯属浪费。
        输入必须是 `featurize_v2(preprocess(image))` 的结果, 否则与部署口径不一致。
        """
        if not self.available:
            return {"probability": None, "verdict": "ML 模型未加载", "threshold": None}
        feats_model = self._pkg.get("features", V1_FEAT_KEYS)
        x = np.asarray(x143, dtype=np.float64).reshape(1, -1)
        if len(feats_model) == 53:
            # 53-D interpretable model = 143-D minus the 90 SRM statistics.
            import featurize_v2 as F2
            names = F2.ALL_FEATURE_NAMES
            idx = [names.index(name) for name in feats_model if name in names]
            if len(idx) != len(feats_model):
                return {"probability": None,
                        "verdict": f"53d 模型特征名与 v2 特征集不匹配 ({len(idx)}/{len(feats_model)})",
                        "threshold": None}
            x = x[:, idx]
        elif len(feats_model) != 143:
            return {"probability": None,
                    "verdict": f"predict_from_v2 只适用于 143/53 维模型 (当前 {len(feats_model)})",
                    "threshold": None}
        return self._score(x)

    # ---- 内部: 打分尾段 (predict / predict_from_v2 共用) ----
    def _score(self, x: np.ndarray) -> dict:
        """特征已就绪: 裁剪 → 模型 → 阈值 → 判词。"""
        feats_model = self._pkg.get("features", V1_FEAT_KEYS)
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
