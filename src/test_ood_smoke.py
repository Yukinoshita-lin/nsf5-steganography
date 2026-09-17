"""OOD 误报率评估的冒烟 + 不变量自测 (2026-09-15)。

为什么需要它
------------
`experiments/ood_eval.py` 产出的是 README 与权威结果表里的**头条数字**
(1514 张真实干净照片上 143d 9.58% / 53d 28.86%), 但它在 CI 里从来没被执行过 ——
原因很实在: 它要 1514 张外部照片。于是这条链只有"代码在那里"这一条保障:

- 语料发现 (`gather_sources`) 写错一个目录名, 只会打印"跳过";
- 汇总 (`summarize`) 的表头变了, 下游 `build_results_table.py` 读列时才会炸;
- 2026-09-15 新加的 `--workers` 并行路径**完全没有测试** —— 它现在是默认路径
  (默认 min(8, CPU))。

本文件用**自造的合成照片**在 CI 里跑通这条链, 并钉住三条不变量:

1. **口径**: 判据必须是 payload 里的阈值 (部署口径), 而不是另设一个;
2. **并行不改数**: workers=1 与 workers=2 的逐图概率必须逐位相同 ——
   这正是 1.6.9 那次 20 分钟 → 1.7 分钟优化必须守住的承诺;
3. **统计自洽**: fp_rate = 误报数/张数, Wilson CI 覆盖点估计,
   汇总里的 ALL 行等于各来源之和。

合成图不能代替真实照片, 所以这里**不**断言任何具体误报率 —— 只断言口径与
统计结构。真实数字的来源仍只有一条: `experiments/ood_eval.py` + 外部语料。
"""
import os
import sys

import numpy as np
import pytest
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
EXP = os.path.join(PROJ, "experiments")
for _p in (SRC, EXP):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MODEL_143 = os.path.join(PROJ, "models", "stego_classifier.joblib")


def _tiny_corpus(dst: str, n: int = 6) -> list:
    """造 n 张**有结构**的灰度照片并转成 JPEG (纯噪声会让 SRM 统计退化)。"""
    os.makedirs(dst, exist_ok=True)
    paths = []
    size = 256
    yy, xx = np.mgrid[0:size, 0:size]
    for i in range(n):
        rng = np.random.default_rng(500 + i)
        img = (90 + 45 * np.sin(xx / (11 + i)) + 30 * np.cos(yy / (17 + i))
               + rng.integers(-8, 9, (size, size)))
        p = os.path.join(dst, f"clean_{i:02d}.jpg")
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(p, quality=92)
        paths.append(p)
    return paths


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    if not os.path.exists(MODEL_143):
        pytest.skip("部署模型不在 (models/ 未随包提供时跳过)")
    d = tmp_path_factory.mktemp("ood_corpus")
    return _tiny_corpus(str(d))


def _evaluate(paths, workers):
    import ood_eval as OE
    return OE.evaluate([("143d", MODEL_143)], {"synth": paths}, (False,),
                       n_sigma=5.0, workers=workers)


def test_rows_match_部署口径(corpus):
    """每张图一行, 且判据等于 payload 阈值 (不是另设的阈值)。"""
    import joblib
    df = _evaluate(corpus, workers=1)
    assert len(df) == len(corpus), f"应有 {len(corpus)} 行, 实际 {len(df)}"
    assert list(df["source"].unique()) == ["synth"]
    assert set(df["model"].unique()) == {"143d"}
    assert df["clip"].unique().tolist() == [False]
    thr_payload = float(joblib.load(MODEL_143)["threshold"])
    assert np.allclose(df["threshold"], thr_payload), \
        "OOD 判据必须用模型 payload 里的部署阈值"
    # pred 必须真的由 prob 与阈值比较得来
    expect = (df["ml_prob"] >= df["threshold"]).astype(int)
    assert (df["pred_stego"].values == expect.values).all()
    assert df["ml_prob"].between(0.0, 1.0).all()


def _run_cli(src_dir, out_dir, workers, timeout=600):
    """跑真的 CLI (`python experiments/ood_eval.py`), 读回它写的逐图 CSV。

    为什么用子进程而不是在 pytest 里直接起进程池: 2026-09-17 的教训 ——
    在 pytest 进程里 `multiprocessing.Pool` 走 fork, 而该进程已经加载过 LightGBM
    (OpenMP 线程池已初始化), 子进程再碰 LightGBM 会**死锁**: CI 的 pytest 作业因此
    从 1 分 44 秒变成挂满 6 小时被取消。CLI 子进程是"干净进程 + spawn",
    既避开这个坑, 又顺带覆盖了参数解析与 CSV 落盘 —— 那两处此前也没有测试。
    """
    import subprocess
    import pandas as pd
    os.makedirs(out_dir, exist_ok=True)
    cmd = [sys.executable, os.path.join(EXP, "ood_eval.py"),
           "--sources", "campus", "--campus-dir", src_dir,
           "--models", f"143d={MODEL_143}", "--clips", "0",
           "--workers", str(workers), "--chunk-timeout", "120",
           "--out-dir", out_dir]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    assert r.returncode == 0, f"CLI 失败:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    return pd.read_csv(os.path.join(out_dir, "ood_eval.csv")), r.stdout


def test_parallel_cli_matches_single_process(corpus, tmp_path):
    """`--workers 2` 与 `--workers 1` 的逐图概率必须逐位相同 (走真的 CLI)。

    这条守的是 1.6.9 的承诺: 并行只改变耗时, 不改变任何数字 —— 而并行现在是
    **默认路径** (min(8, CPU))。
    """
    src = tmp_path / "corpus"
    src.mkdir(exist_ok=True)
    for p in corpus:
        (src / os.path.basename(p)).write_bytes(open(p, "rb").read())
    df1, _ = _run_cli(str(src), str(tmp_path / "out1"), workers=1)
    df2, _ = _run_cli(str(src), str(tmp_path / "out2"), workers=2)
    cols = ["model", "clip", "source", "photo_name", "ml_prob", "threshold", "pred_stego"]
    a = df1[cols].sort_values("photo_name").reset_index(drop=True)
    b = df2[cols].sort_values("photo_name").reset_index(drop=True)
    assert len(a) == len(corpus)
    assert a.equals(b), f"并行改变结果:\n{a.compare(b)}"


def test_parallel_timeout_raises_instead_of_hanging(corpus, tmp_path):
    """并行卡住必须是**报错**, 不能是"永远在跑"。

    2026-09-17: 一次 fork 死锁让 CI 的 pytest 作业挂了 6 小时才被取消。
    超时参数 (`--chunk-timeout`) 是给这类事故装的断路器: 这里把上限压到 1 秒,
    进程池必然来不及返回, 必须抛错并以非零码退出。
    """
    import subprocess
    src = tmp_path / "corpus_t"
    src.mkdir(exist_ok=True)
    for p in corpus[:2]:
        (src / os.path.basename(p)).write_bytes(open(p, "rb").read())
    cmd = [sys.executable, os.path.join(EXP, "ood_eval.py"),
           "--sources", "campus", "--campus-dir", str(src),
           "--models", f"143d={MODEL_143}", "--clips", "0", "--workers", "2",
           "--chunk-timeout", "1", "--out-dir", str(tmp_path / "out_t")]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    assert r.returncode != 0, "超时没有报错, 说明断路器没接上"
    assert "没有返回任何分片" in (r.stdout + r.stderr)


def test_summary_is_self_consistent(corpus):
    """汇总表: 张数、误报率、Wilson CI、ALL 行都要自洽。"""
    import ood_eval as OE
    df = _evaluate(corpus, workers=1)
    s = OE.summarize(df)
    assert set(["model", "clip_outliers", "source", "n_photos", "n_false_positive",
                "fp_rate", "fp_ci_lo", "fp_ci_hi", "median_prob", "protocol"]) <= set(s.columns)
    all_row = s[(s["source"] == "ALL") & (s["model"] == "143d")].iloc[0]
    assert int(all_row["n_photos"]) == len(corpus)
    assert int(all_row["n_false_positive"]) == int(df["pred_stego"].sum())
    assert all_row["fp_rate"] == pytest.approx(
        int(all_row["n_false_positive"]) / int(all_row["n_photos"]), abs=5e-5)
    assert all_row["fp_ci_lo"] <= all_row["fp_rate"] <= all_row["fp_ci_hi"]
    # 协议串必须写清"干净图 + 灰度 512 + 与 payload 阈值比较", 否则读者无法判断口径
    proto = str(all_row["protocol"])
    assert "clean" in proto and "LANCZOS" in proto and "threshold" in proto


def test_source_rows_sum_to_all(corpus):
    """按来源分组的行加起来必须等于 ALL 行 (不能悄悄丢样本)。"""
    import ood_eval as OE
    df = _evaluate(corpus, workers=1).copy()
    # 把语料拆成两个来源, 走的是真实的"多源 + ALL"汇总路径
    df.loc[df.index[: len(corpus) // 2], "source"] = "synthA"
    df.loc[df.index[len(corpus) // 2:], "source"] = "synthB"
    s = OE.summarize(df)
    per_source = s[(s["source"] != "ALL") & (s["model"] == "143d")]
    all_row = s[(s["source"] == "ALL") & (s["model"] == "143d")].iloc[0]
    assert int(per_source["n_photos"].sum()) == int(all_row["n_photos"])
    assert int(per_source["n_false_positive"].sum()) == int(all_row["n_false_positive"])


def test_wilson_ci_sanity():
    """Wilson 区间: 覆盖点估计、随 n 变窄、端点不越界。"""
    import ood_eval as OE
    for k, n in [(0, 10), (1, 10), (5, 10), (9, 10), (10, 10), (95, 1000)]:
        lo, hi = OE.wilson_ci(k, n)
        assert 0.0 <= lo <= k / n <= hi <= 1.0, (k, n, lo, hi)
    w_small = OE.wilson_ci(1, 10)
    w_big = OE.wilson_ci(100, 1000)
    assert (w_big[1] - w_big[0]) < (w_small[1] - w_small[0]), "n 越大区间应越窄"
    lo, hi = OE.wilson_ci(0, 0)
    assert lo != lo and hi != hi        # nan: 没有样本就没有区间


def test_list_images_and_missing_source_is_loud(tmp_path, capsys):
    """语料发现: 只认图像扩展名, 缺目录时打印原因而不是静默少行。"""
    import ood_eval as OE
    d = tmp_path / "pics"
    (d / "sub").mkdir(parents=True)
    _tiny_corpus(str(d), n=2)
    (d / "notes.txt").write_text("not an image", encoding="utf-8")
    Image.fromarray(np.zeros((64, 64), np.uint8)).save(d / "sub" / "nested.png")
    found = OE.list_images(str(d), 0)
    assert len(found) == 3, found            # 2 jpg + 1 嵌套 png, txt 不算
    assert all(os.path.splitext(p)[1].lower() in
               (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".pgm") for p in found)

    class A:
        sources = "div2k"
        campus_dir = str(tmp_path / "nope")
        div2k_dir = str(tmp_path / "nope2")
        alaska_dir = str(tmp_path / "nope3")
        campus_n = div2k_n = alaska_n = 0

    got = OE.gather_sources(A())
    out = capsys.readouterr().out
    assert got == {}
    assert "跳过" in out and "DIV2K" in out, "缺语料必须打印原因"
