# -*- mode: python ; coding: utf-8 -*-
"""nsf5stego 打包规格: 同一份代码出两个 onedir ——

  * nsf5stego      控制台入口 (src/cli.py): embed / extract / analyze / gui
  * nsf5stego-gui  窗口化入口 (scripts/gui_entry.py): 双击即开图形界面

构建走 `python scripts/build_exe.py` (它会先生成 build/version.txt,
再调 `python -m PyInstaller --distpath build/exe --workpath build/pyinstaller
nsf5stego.spec`), 不要直接改本文件里的路径假设。

三条实证教训 (2026-09-30 冒烟, 详见 docs/PACKAGING.md):
  1. 模型必须显式 add-data 到 nsf5_models/ 子目录 —— collect-data 遇到
     package-dir 映射会把文件平铺进 _internal 根, ml_predict 找不到;
  2. joblib/pandas/sklearn 是 ml_predict 的函数内延迟导入, 静态分析看不见
     (sklearn 甚至只在反序列化 pickle 时才被 import), 必须 hidden-import;
  3. lightgbm 的原生 DLL 进不了 PYZ, 必须 collect_all; 而 sklearn 用
     collect_all 会把包撑到 3GB, 只能走 hidden-import + 官方钩子。
"""
import glob
import os

from PyInstaller.utils.hooks import collect_all

# ---- 数据: 白名单模型 (models/ 下还有 .bak 训练残留, 不能 glob) + 版本号 ----
datas = [
    ("models/stego_classifier.joblib", "nsf5_models"),
    ("models/stego_classifier_v2_jpeg_lgb_51d.joblib", "nsf5_models"),
    ("models/stego_classifier.card.json", "nsf5_models"),
    ("models/stego_classifier_v2_jpeg_lgb_51d.card.json", "nsf5_models"),
    ("build/version.txt", "."),
]

# ---- C++ 加速库 (可选): build_exe.py 已尽力编译, 缺文件则静默跳过 ----
for _pat in ("cpp/nsf5embed.dll", "cpp/fsfeatures.dll",
             "cpp/libnsf5embed.so", "cpp/libfsfeatures.so",
             "cpp/libnsf5embed.dylib", "cpp/libfsfeatures.dylib"):
    for _p in glob.glob(os.path.join(SPECPATH, _pat)):
        datas.append((os.path.relpath(_p, SPECPATH), "cpp"))

hiddenimports = ["gui", "ml_predict", "joblib", "pandas", "sklearn"]
binaries = []
_lgb_datas, _lgb_binaries, _lgb_hidden = collect_all("lightgbm")
datas += _lgb_datas
binaries += _lgb_binaries
hiddenimports += _lgb_hidden

excludes = ["IPython", "torch", "x86_64"]  # xgboost/torch 仅训练用, 排除瘦身

a_cli = Analysis(
    ["src/cli.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure)
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    exclude_binaries=True,
    name="nsf5stego",
    console=True,
    icon=None,
    version="build/version_info.txt",
)

a_gui = Analysis(
    ["scripts/gui_entry.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz_gui = PYZ(a_gui.pure)
exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    exclude_binaries=True,
    name="nsf5stego-gui",
    console=False,
    icon=None,
    version="build/version_info.txt",
)

# 两个 exe 共享一个 onedir: DLL/模型只有一份, 体积比两个 COLLECT 减半
COLLECT(
    exe_cli,
    exe_gui,
    a_cli.binaries,
    a_cli.datas,
    a_gui.binaries,
    a_gui.datas,
    strip=False,
    upx=False,
    name="nsf5stego",
)
