PY ?= python3
PIP ?= $(PY) -m pip
CXX ?= g++

# C++ 加速库: 产物不入库, 用 `make cpp` 现场编译。后缀按平台决定。
ifeq ($(OS),Windows_NT)
  CXXFLAGS_CPP ?= -O2 -shared -static
  LIB_SUFFIX   := .dll
else
  UNAME_S := $(shell uname -s)
  CXXFLAGS_CPP ?= -O2 -shared -fPIC
  ifeq ($(UNAME_S),Darwin)
    LIB_SUFFIX := .dylib
  else
    LIB_SUFFIX := .so
  endif
endif

.PHONY: help install test core steg fp pipeline pytest pyfeatures cpp cpp-clean \
	e2e gui notebooks dataset docker web-convert web-build thesis-data thesis-figs

help:
	@echo "Targets:"
	@echo "  make install      - editable install (uses $(PY))"
	@echo "  make test         - core + steganalysis + false-positive + features"
	@echo "  make pytest       - run the whole suite through pytest"
	@echo "  make cpp          - build the C++ accelerators into cpp/ (optional)"
	@echo "  make thesis-figs  - rebuild thesis figures from thesis/data/*.csv"
	@echo "  make e2e          - full embed/decode/analyze demo"
	@echo "  make notebooks    - regenerate per-chapter notebooks"
	@echo "  make dataset      - download BOSSbase 1.01"
	@echo "  make docker       - build & run the teaching JupyterLab image"
	@echo "  make web-convert  - regenerate bilingual web markdown from DOCX"
	@echo "  make web-build    - build both Jupyter Books"

install:
	$(PIP) install -e .

core:
	$(PY) src/test_core.py

steg:
	$(PY) src/test_steg.py

fp:
	$(PY) src/test_false_positive.py

pipeline:
	$(PY) src/test_pipeline.py

pytest:
	$(PY) -m pytest -q

pyfeatures:
	$(PY) -c "import sys; sys.path.insert(0, 'src'); \
import numpy as np; \
from py_features import features; \
from featurize_v2 import featurize_v2; \
a = np.random.default_rng(0).integers(0, 256, (128, 128), dtype=np.uint8); \
assert len(features(a)) == 11; \
assert featurize_v2(a).shape == (143,); \
print('pure-python features OK (no DLL required)')"

test: core steg fp pipeline pyfeatures

# C++ 加速库 (可选): 缺失时 Python 侧自动回退到等价实现, 功能不变、只是慢些。
# 编译逻辑收在 scripts/build_cpp.py, 与 CI 共用同一套平台规则。
cpp:
	$(PY) scripts/build_cpp.py
	@echo "自检: $(PY) src/fsfeatures.py && $(PY) src/cppembed.py"

cpp-clean:
	rm -f cpp/fsfeatures.dll cpp/nsf5embed.dll \
	      cpp/fsfeatures.so cpp/nsf5embed.so \
	      cpp/fsfeatures.dylib cpp/nsf5embed.dylib

e2e:
	$(PY) src/run_e2e.py

gui:
	$(PY) src/gui.py

notebooks:
	$(PY) teaching/build_notebooks.py

dataset:
	$(PY) scripts/download_datasets.py --out data/BOSSbase_1.01

# 论文实验: 先出数据(含 CNN 训练, 约 2 小时), 再出图。
# 只要已有 thesis/data/*.csv, 单独跑 `make thesis-figs` 即可。
thesis-figs:
	$(PY) thesis/exp/gen_figs.py

thesis-data:
	$(PY) thesis/exp/featurize_bossbase_npz.py
	$(PY) thesis/exp/run_cnn_sota.py
	$(PY) thesis/exp/eval_cnn_checkpoint.py
	$(PY) thesis/exp/sota_compare.py
	$(PY) thesis/exp/merge_sota_table.py

docker:
	docker compose up --build

web-convert:
	$(PY) teaching/web/docx2md.py --docx "thesis/学习手册-从零读懂nsF5隐写项目.docx" --out teaching/web/zh --lang zh
	$(PY) teaching/web/docx2md.py --docx "thesis/Learning-Handbook-From-Zero-to-nsF5-Steganography.docx" --out teaching/web/en --lang en
	$(PY) teaching/web/add_lang_switch.py

web-build:
	jupyter-book build teaching/web/zh
	jupyter-book build teaching/web/en
