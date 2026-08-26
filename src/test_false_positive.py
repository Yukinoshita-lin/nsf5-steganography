"""盲隐写分析 误判(假阳性)回归测试。

若干类"未隐写"的普通 8bit 图, 不应被高概率判为隐写。
若某图确实无法可靠判定, 允许返回 abstain 判读(中位概率)而不得误报高概率。
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import steganalysis as SA

def clean_images():
    rng = lambda s: np.random.default_rng(s)
    G = rng(1)
    y = np.linspace(0, 220, 256)[None, :]; x = np.linspace(-30, 70, 256)[:, None]
    gradient = np.clip(110 + y + x + G.integers(-4, 5, (256, 256)), 8, 255).astype(np.uint8)

    full_noise = rng(2).integers(0, 256, (256, 256), dtype=np.uint8)

    flat = np.full((256, 256), 128, np.uint8)
    flat[:, :50] = 200; flat[:, -40:] = 40
    flat = flat + rng(3).integers(0, 2, (256, 256), dtype=np.uint8)

    photo = np.clip(90 + 60*np.sin(np.mgrid[0:256,0:256][1]/24)
                    + 40*np.cos(np.mgrid[0:256,0:256][0]/31)
                    + rng(4).integers(-2, 3, (256, 256)), 10, 245).astype(np.uint8)

    text = np.full((256, 256), 245, np.uint8)
    rt = rng(5)
    for i in range(0, 240, 18):
        text[i:i+3, 20:236] = rt.integers(0, 80, (3, 216)).astype(np.uint8)

    return {"渐变(自然图)": gradient, "纯噪声": full_noise,
            "平坦色块(UI)": flat, "低频照片": photo, "白底黑字文档": text}

def run():
    ok = True
    for name, img in clean_images().items():
        r = SA.analyze(img)
        p = r["stego_probability"]
        bad = p >= 0.65                      # 误报高概率
        abstain = r["verdict"].startswith("无法可靠判定")
        flag = "误报!" if bad else ("abstain" if abstain else "ok")
        if bad:
            ok = ok
        print(f"  {name:<12} Gn={r['RS_Gn']:.3f} LSB熵={r['lsb_diff_entropy']:.3f} "
              f"prob={p:.2f} {r['verdict']}  [{flag}]")
    # 允许 abstain, 但绝不允许把未隐写图判为高概率隐写
    assert all(SA.analyze(img)["stego_probability"] < 0.65
               for img in clean_images().values()), "存在干净图被误判为高概率隐写"
    print("[OK] 干净图均未被误判为高概率隐写")

if __name__ == "__main__":
    run()