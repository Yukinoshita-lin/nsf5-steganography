"""盲隐写分析自测: 干净平滑图 vs nsF5 嵌入图 的区分度。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import steganalysis as SA
from ns5_core import embed_string

def smooth(shape=(256, 256)):
    y = np.linspace(0, 200, shape[1])[None, :]
    x = np.linspace(0, 80, shape[0])[:, None]
    return np.clip(120 + y + x, 0, 255).astype(np.uint8)

def run():
    clean = smooth()
    # 较高密度嵌入, 使 RS 缺口可检测。消息长度须在容量内 (B2: 超载会明确报错)。
    # 256x256 p=3 的正文容量约 3494 字节, 用 2500 字符既接近容量又被安全容纳。
    stego, rep, nb = embed_string(clean, "S" * 2500, method="nsF5", p=3)
    # 校验往返一致, 避免之前"静默截断 -> 解码失败"的假阳性测试。
    from ns5_core import extract_string
    assert extract_string(stego, method="nsF5", p=3) == "S" * 2500
    ch = int((stego != clean).sum())
    print(f"嵌入比特 {nb}, 改动像素 {ch} ({ch/clean.size:.3f})")
    rc = SA.analyze(clean)
    rs = SA.analyze(stego)
    for name, r in (("干净图", rc), ("含密图", rs)):
        print(f"  {name}: Gn={r['RS_Gn']:.3f} Gr={r['RS_Gr']:.3f} "
              f"chi2_p={r['chi2_pvalue']:.3f} rate={r['est_rate']:.3f} "
              f"prob={r['stego_probability']:.3f} -> {r['verdict']}")
    assert rc["stego_probability"] < 0.5, "干净图误判过高"
    assert rs["stego_probability"] >= 0.5, "含密图未检出"

def test_steganalysis_separates_clean_from_stego():
    """pytest 入口。`python src/test_steg.py` 仍然可用。"""
    run()


if __name__ == "__main__":
    run()
    print("[OK] 隐写分析可区分 干净/含密 图像")