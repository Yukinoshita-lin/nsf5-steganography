"""实验链冒烟测试: 造图 → make_dataset → train_model → run_e2e。

为什么需要它 (2026-09-14)
------------------------
覆盖率一测就露馅: 核心算法 (`ns5_core` 88%、`steganalysis` 90%) 有测试, 但
**三条用户入口是 0%** —— `make_dataset.py`、`train_model.py`、`run_e2e.py`。
也就是说"按 README 跑一遍 数据→训练→端到端"这条路, CI 从来没验证过。

实现选择: 直接**在进程内**调用各自的 `main()` (而不是起子进程)。原因是
coverage 默认不追踪子进程 —— 起子进程虽然也"跑通"了, 但覆盖率仍是 0%,
等于白测。CLI 的参数解析另用 `--help` 冒烟一次, 保证文档里的命令形态没坏。

所有产物都写到临时目录, 唯一的例外是 `make_dataset` 按设计写进
`data/dataset_<name>.csv` (会被清理) 与 `run_e2e` 写进 `output/` (已在
.gitignore 里)。
"""
import csv
import importlib
import io
import os
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

N_PHOTOS = 12
WORK = (192, 192)
V1_FEATURES = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn", "chi2_pvalue",
               "diff_entropy", "lsb_diff_entropy", "median_prefix_p", "chi2_stat"]
META = ["label", "photo_id", "variant", "method", "p", "density", "changed_frac"]


def _make_photos(dst: str, n: int = N_PHOTOS) -> str:
    """造 n 张**有结构**的灰度照片 (纯噪声会让 RS/SRM 统计退化)。"""
    os.makedirs(dst, exist_ok=True)
    size = WORK[0]
    for i in range(n):
        rng = np.random.default_rng(1000 + i)
        yy, xx = np.mgrid[0:size, 0:size]
        img = (70 + 40 * np.sin(xx / (9 + i)) + 35 * np.cos(yy / (13 + i))
               + rng.integers(-6, 7, (size, size)))
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(
            os.path.join(dst, f"photo_{i:02d}.jpg"), quality=95)
    return dst


def _minimal_variants():
    import make_dataset as MD
    return [v for v in MD.DEFAULT_VARIANTS if v[0] != "lsb" and v != ("nsF5", 3, 0.40)]


def _build_smoke_dataset(tmp_path, name: str) -> str:
    """进程内调用 make_dataset.main(), 返回 CSV 路径。"""
    import make_dataset as MD
    photos = _make_photos(str(tmp_path / "photos"))
    MD.main(photos, WORK, name, 0, 1, "none", "v1", _minimal_variants())
    csv_path = os.path.join(PROJ, "data", f"dataset_{name}.csv")
    assert os.path.exists(csv_path), "make_dataset 没有写出 CSV"
    return csv_path


# --------------------------------------------------------------------------- #
#  1) make_dataset: 结构契约
# --------------------------------------------------------------------------- #
def test_make_dataset_produces_the_declared_schema(tmp_path):
    name = "ci_smoke_schema"
    csv_path = _build_smoke_dataset(tmp_path, name)
    try:
        with io.open(csv_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        header, data = rows[0], rows[1:]
        assert header[:11] == V1_FEATURES, f"v1 特征列不对: {header[:11]}"
        assert header[11:] == META, f"元数据列不对: {header[11:]}"
        # minimal = 6 档变体 → 每张源图 1 干净 + 6 含密
        assert len(data) == N_PHOTOS * 7, f"样本数应为 {N_PHOTOS*7}, 实际 {len(data)}"
        ids = {r[12] for r in data}                     # photo_id
        assert len(ids) == N_PHOTOS, f"源图数应为 {N_PHOTOS}, 实际 {len(ids)}"
        labels = [r[11] for r in data]                  # label
        assert labels.count("0") == N_PHOTOS, "干净样本数不等于源图数"
        assert labels.count("1") == N_PHOTOS * 6, "含密样本数不等于 源图×6"
        print(f"[OK] make_dataset: {N_PHOTOS} 张源图 -> {len(data)} 行, 结构符合声明")
    finally:
        os.remove(csv_path)


def test_make_dataset_cli_surface():
    """文档里写的是 CLI 形态 (`python src/make_dataset.py <目录> 512x512 --out ...`),
    这里只验证参数解析没坏 —— 真正跑数据在上面那个用例里 (进程内)。"""
    r = subprocess.run([sys.executable, "src/make_dataset.py", "--help"],
                       cwd=PROJ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-400:]
    for flag in ("--out", "--feature-set", "--variants", "--workers", "--preprocess"):
        assert flag in r.stdout, f"CLI 少了 {flag}"
    print("[OK] make_dataset --help: 文档里的参数都在")


# --------------------------------------------------------------------------- #
#  2) train_model: 小数据上跑完整训练
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_train_model_runs_on_smoke_dataset(tmp_path, monkeypatch):
    name = "ci_smoke_train"
    csv_path = _build_smoke_dataset(tmp_path, name)
    metrics = tmp_path / "metrics.csv"
    det = tmp_path / "detection.csv"
    model = tmp_path / "model.joblib"
    monkeypatch.setenv("DS_FILES", f"dataset_{name}.csv")
    monkeypatch.setenv("OUT_MODEL", str(model))
    # 指标走临时路径: 冒烟不能污染 docs/RESULTS.md 读的权威表
    monkeypatch.setenv("METRICS_CSV", str(metrics))
    monkeypatch.setenv("DETECTION_CSV", str(det))
    try:
        import train_model
        importlib.reload(train_model)          # DATA_FILES 在导入时读环境变量
        train_model.main(seed=0)
        assert model.exists(), "train_model 没有写出模型"
        assert metrics.exists(), "train_model 没有写出指标 CSV"
        with io.open(metrics, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert rows, "指标 CSV 为空"
        auc = float(rows[-1]["held_out_auc"])
        assert 0.0 <= auc <= 1.0, f"AUC 越界: {auc}"
        assert rows[-1]["model"], "指标里没记录选中的模型"
        print(f"[OK] train_model: 小数据上跑通 (选中 {rows[-1]['model']}, AUC={auc:.3f})")
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
    authoritative = os.path.join(PROJ, "experiments", "data", "train_model_metrics.csv")
    if os.path.exists(authoritative):
        txt = io.open(authoritative, encoding="utf-8").read()
        assert f"dataset_{name}" not in txt, "冒烟测试污染了权威指标表"


# --------------------------------------------------------------------------- #
#  3) run_e2e: 端到端闭环
# --------------------------------------------------------------------------- #
def test_run_e2e_closes_the_loop(monkeypatch):
    cwd = os.getcwd()
    os.chdir(PROJ)                      # run_e2e 用相对路径 img/cover.png
    try:
        import run_e2e
        importlib.reload(run_e2e)
        run_e2e.main()                  # 抛异常即失败
    finally:
        os.chdir(cwd)
    print("[OK] run_e2e: 嵌入/解码/分析闭环通过 (含效率图)")


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        test_make_dataset_produces_the_declared_schema(Path(td))
        test_make_dataset_cli_surface()
        test_train_model_runs_on_smoke_dataset(Path(td), pytest.MonkeyPatch())
    test_run_e2e_closes_the_loop(pytest.MonkeyPatch())
    print("\n全部通过")
