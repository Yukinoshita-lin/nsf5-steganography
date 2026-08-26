"""
有监督 ML 隐写判定 —— 对单张图像给出"含密概率"。

- 预处理与训练一致: 转灰度 → LANCZOS 缩放到 512x512
- 特征: 全部由 C++ 库 fsfeatures.dll 提取 (11 维)
- 模型: models/stego_classifier.joblib (训练自校园照片 clean/stego 数据集)
- 阈值: 默认用 Youden 平衡点; 可用 low_fp 档(低误报但检出极弱)

说明: 对真 JPEG 照片, LSB 位平面天然近乎随机, 弱密度 nsF5 嵌入的
统计足印很弱, ML 概率只是辅助判读, 与启发式(S)交叉印证。
"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(PROJ, "models", "stego_classifier.joblib")

FEAT_KEYS = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
             "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
             "median_prefix_p", "chi2_stat"]
WORK_SIZE = (512, 512)


class MLPredictor:
    def __init__(self, model_path: str = MODEL_PATH, sensitivity: str = "均衡"):
        try:
            from joblib import load
            pkg = load(model_path)
        except Exception:
            pkg = None
        self._pkg = pkg
        self.sensitivity = sensitivity

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
        from fsfeatures import get_lib
        a = self.preprocess(image)
        feats = get_lib().features(a)
        x = np.array([feats[k] for k in FEAT_KEYS], dtype=np.float64).reshape(1, -1)
        p = float(self._pkg["model"].predict_proba(x)[0, 1])
        thr = self._threshold()
        verdict = ("判定为含密 (ML)" if p >= thr else
                   "判定为干净 (ML)" if p < thr * 0.9 else "ML: 边界不清")
        return {"probability": p, "verdict": verdict, "threshold": thr}


_predictor = None
def get_predictor(sensitivity: str = "均衡") -> MLPredictor:
    global _predictor
    if _predictor is None or _predictor.sensitivity != sensitivity:
        _predictor = MLPredictor(sensitivity=sensitivity)
    return _predictor


if __name__ == "__main__":
    import numpy as np
    p = get_predictor()
    print("模型可用:", p.available, "路径:", MODEL_PATH)
    if p.available:
        img = np.random.default_rng(0).integers(0, 256, (256, 256), dtype=np.uint8)
        print("随机图(应为干净)概率:", p.predict(img)["probability"])