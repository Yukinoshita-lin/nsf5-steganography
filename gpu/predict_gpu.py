"""predict_gpu —— 单张图像的 GPU 隐写检测 (统计特征 + LogisticRegression)。

用法:
    python gpu/predict_gpu.py <图像路径> [<路径>...]
"""
from __future__ import annotations
import os, sys
import numpy as np
import joblib
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import featurize_gpu as FG

PROJ = os.path.dirname(HERE)
_MODEL = os.path.join(PROJ, "models", "steg_classifier_gpu.joblib")
SIZE = 512   # 与训练一致


def _load(path: str, size: int = SIZE) -> np.ndarray:
    a = np.asarray(Image.open(path).convert("L").resize((size, size), Image.LANCZOS),
                   dtype=np.uint8)
    return a


class GpuDetector:
    def __init__(self, model_path: str = _MODEL):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"未找到模型 {model_path}, 请先运行: python gpu/train_ml_gpu.py")
        st = joblib.load(model_path)
        self.clf = st["model"]
        self.threshold = float(st.get("threshold", 0.5))
        self.auc = float(st.get("auc", float("nan")))

    def proba(self, img: np.ndarray) -> float:
        """img: uint8 (H,W) 灰度 或 (H,W,3)。返回含密概率。"""
        feat = FG.extract_features_gpu(img[None], chunk=1)[0]
        return float(self.clf.predict_proba(feat[None])[:, 1][0])

    def judge(self, p: float) -> str:
        return (f"含密嫌疑 (prob={p:.3f} >= thr={self.threshold:.3f})"
                if p >= self.threshold else
                f"疑似干净 (prob={p:.3f} < thr={self.threshold:.3f})")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    det = GpuDetector()
    print(f"GPU={FG.pick_gpu()}  阈值 thr={det.threshold:.3f}  验证AUC={det.auc:.3f}")
    for p in argv:
        if not os.path.exists(p):
            print(f"  [跳过] 不存在: {p}")
            continue
        prob = det.proba(_load(p))
        print(f"  {os.path.basename(p):<26} prob={prob:.3f}  -> {det.judge(prob)}")


if __name__ == "__main__":
    main()