"""JPEG 压缩域 (量化 DCT 系数) nsF5 桥接层 —— 把姊妹项目 yccstego 接入主线。

为什么是"桥接"而不是把代码复制进来
---------------------------------
yccstego 是独立仓库、独立发版的 PyPI 包 (自实现 JPEG DCT + Huffman 编解码),
主包通过带 python_version 标记的依赖声明引入 (>=3.10; 主包整体仍支持 3.9)。
本模块只做三件事:

1. 统一入口: 嵌入 / 提取 / 分析 / 预览四个函数, GUI 与 CLI 都走这里,
   不直接 import yccstego —— 依赖缺失时的降级提示集中在 _api() 一处;
2. 统一口径: report 字段沿用 yccstego 原样 (carriers_changed / capacity_bits),
   保留"系数"措辞, 不与像素域的 cover_changed (改的是像素) 混用;
3. 教学口径: 像素域 (ns5_core.py) 改的是灰度像素 LSB; 压缩域改的是量化 Y 块
   的非零 AC 系数 —— F5 的减幅修改 (+3→+2) 与湿纸避让 (|c|==1 不碰) 发生在
   系数上, 这才是教科书里的 nsF5。

确定性契约 (0.2.0 起, 影响"实验重跑"语义, 见 experiment.py)
-------------------------------------------------
- 像素域: 湿纸求解的遍历种子由输入派生, 相同输入逐字节复现;
- 压缩域: yccstego 0.2.0 起与主线同用输入派生种子, **同样逐字节复现**。
  重跑契约按版本分档: 档案记录建档时的 yccstego 版本, 重跑时版本一致走
  字节级校验, 版本不同自动退回"提取一致"并如实标注 (旧版 0.1.4 的嵌入
  含全局随机数, 跨版本只承诺提取一致)。
"""
from __future__ import annotations

import io
import os
import sys

import numpy as np

_INSTALL_HINT = (
    "未安装 JPEG 压缩域依赖 yccstego。安装方式:\n"
    "  pip install yccstego            (源码运行 / Python>=3.10)\n"
    "  pip install nsf5stego           (安装版会按 Python 版本自动带上)\n"
    "Python 3.9 不支持压缩域, 请用像素域 (默认)。")

_SHADOW_HINT = ("(检测到仓库内同名目录: 自动修复未生效, 请手动执行 "
                "pip install -e ./yccstego)")


class JpegDomainUnavailable(RuntimeError):
    """yccstego 依赖缺失 (或被仓库同名目录遮蔽) 时 raised。"""


_cache = {"tried": False, "api": None, "error": None}


def _vendored_root():
    """源码 checkout 里的 yccstego 项目根 (其下 yccstego/__init__.py 存在)。

    仓库布局: <root>/src/jpegstego.py 与 <root>/yccstego/(独立 git checkout)。
    pip 安装 / PyInstaller 冻结布局下不存在, 返回 None。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(os.path.dirname(here), "yccstego")
    if os.path.isfile(os.path.join(cand, "yccstego", "__init__.py")):
        return cand
    return None


def _import_api():
    from yccstego import api as _a
    return _a


def _api():
    """惰性导入 yccstego.api, 结果缓存; 失败时自愈一次再报可行动的错。

    自愈的必要性 (2026-10-03 用户实测): 仓库根目录下有个同名 `yccstego/`
    目录 (姊妹项目的 git checkout, 无 __init__.py), 任何 cwd=仓库根 的运行
    都会先把它解析成**命名空间包**; pip 的 PEP 660 editable 安装只可靠地
    映射子模块名, 换一个没装它的解释器, `from yccstego import api` 就报
    "cannot import name 'api' (unknown location)"。修法: 检测到源码
    checkout 的真包目录时, 把它插到 sys.path 最前 (带 __init__.py 的常规
    包在扫描中必胜过命名空间候选), 逐出已缓存的命名空间模块后重试。"""
    if not _cache["tried"]:
        _cache["tried"] = True
        api, err = None, None
        try:
            api = _import_api()
        except Exception as e:
            err = e
            root = _vendored_root()
            if root is not None:
                if root not in sys.path:
                    sys.path.insert(0, root)
                for name in [m for m in list(sys.modules)
                             if m == "yccstego" or m.startswith("yccstego.")]:
                    del sys.modules[name]
                try:
                    api = _import_api()
                    err = None
                except Exception as e2:
                    err = e2
        if api is None:
            _cache["error"] = (_INSTALL_HINT + "\n导入错误: " + str(err)
                               + ("\n" + _SHADOW_HINT if _vendored_root() is not None else ""))
            # 失败不永久缓存: 用户按提示装好依赖后, 再点一次即可, 无需重启
            _cache["tried"] = False
        else:
            _cache["api"] = api
    if _cache["api"] is None:
        raise JpegDomainUnavailable(_cache["error"])
    return _cache["api"]


def available() -> bool:
    """压缩域是否可用 (依赖是否装好)。CLI/GUI 据此决定禁用还是降级提示。"""
    try:
        _api()
        return True
    except JpegDomainUnavailable:
        return False


def unavailable_reason() -> str:
    """返回不可用的原因文本; 可用时返回空串。"""
    try:
        _api()
        return ""
    except JpegDomainUnavailable as e:
        return str(e)


def embed_jpeg(source, text: str, p: int = 3, password: str = "",
               quality: int = 85, truncate: bool = False, trace: bool = False):
    """在 JPEG 压缩域嵌入文本。source: 图像路径 / RGB ndarray / 图像字节。

    返回 (jpg_bytes, report)。report 字段 (yccstego 原样):
      cover_hash        色度系数 SHA-256 前 16 字节 (篡改感知锚点)
      carriers_changed  被修改的 DCT 系数个数
      capacity_bits     正文池理论容量 (bit)
      head_pool/body_pool  头部池 / 正文池载体系数个数
      wet_points        嵌入前载体中 |c|=1 的湿点个数
      truncated/embedded_chars  是否截断 / 实际写入字符数
      changes           trace=True 时: 每个被修改系数的轨迹
                        (cell/block/rc/pool/kind/from/to), 供可视化
    消息超容量时: truncate=False 抛 yccstego.nsf5.CapacityError。
    """
    jpg, rep = _api().embed_bytes(source, text, p=p, password=password,
                                  quality=quality, truncate=truncate, trace=trace)
    return jpg, dict(rep)


def ycc_version():
    """正在**执行的** yccstego 代码的版本字符串; 取不到返回 None。

    为什么不直接读 importlib.metadata: editable 安装的 dist-info 版本冻结在
    `pip install -e` 那一刻, 源码升版后它会撒谎 (实测: 源码 0.2.0 / dist-info
    仍 0.1.4)。真包的 __init__.py 可能没被执行 (根名被遮蔽时), 所以从文件里
    解析 __version__, dist-info 只作兜底。"""
    try:
        api = _api()
        init_py = os.path.join(os.path.dirname(os.path.abspath(api.__file__)),
                               "__init__.py")
        with open(init_py, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("__version__"):
                    val = line.split("=", 1)[1].split("#", 1)[0].strip().strip("\"'")
                    if val:
                        return val
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("yccstego")
    except Exception:
        return None


def ycc_version_tuple():
    """ycc_version() 的 (major, minor, patch) 元组; 取不到返回 None。"""
    v = ycc_version()
    if not v:
        return None
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except ValueError:
        return None


def extract_jpeg(jpg_bytes, p: int = 3, password: str = ""):
    """从 JPEG 字节提取文本。返回 (message|None, cover_hash_hex, tampered, head_match)。"""
    return _api().extract_bytes(jpg_bytes, p=p, password=password)


def analyze_jpeg(jpg_bytes, sensitivity: str = "均衡"):
    """JPEG 域盲分析: DCT 系数 magnitude-1 指纹为主信号, 卡方为弱佐证。

    返回 dict (yccstego 原样): ok / n_ac / unit_frac / stego_probability_dct /
    verdict, 外加像素域参照 pix_probability / pix_verdict。"""
    return _api().analyze_bytes(jpg_bytes, sensitivity=sensitivity)


def decode_preview(jpg_bytes) -> np.ndarray:
    """JPEG 字节 → RGB uint8 ndarray (GUI 预览用, 不落盘)。"""
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(bytes(jpg_bytes))).convert("RGB"))
