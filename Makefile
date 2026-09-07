PY ?= python3
PIP ?= $(PY) -m pip

.PHONY: help install test core steg fp pyfeatures e2e gui notebooks \
	dataset docker web-convert web-build

help:
	@echo "Targets:"
	@echo "  make install      - editable install (uses $(PY))"
	@echo "  make test         - core + steganalysis + false-positive + features"
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

pyfeatures:
	$(PY) -c "import sys; sys.path.insert(0, 'src'); \
import numpy as np; \
from py_features import features; \
from featurize_v2 import featurize_v2; \
a = np.random.default_rng(0).integers(0, 256, (128, 128), dtype=np.uint8); \
assert len(features(a)) == 11; \
assert featurize_v2(a).shape == (143,); \
print('pure-python features OK (no DLL required)')"

test: core steg fp pyfeatures

e2e:
	$(PY) src/run_e2e.py

gui:
	$(PY) src/gui.py

notebooks:
	$(PY) teaching/build_notebooks.py

dataset:
	$(PY) scripts/download_datasets.py --out data/BOSSbase_1.01

docker:
	docker compose up --build

web-convert:
	$(PY) teaching/web/docx2md.py --docx "thesis/学习手册-从零读懂nsF5隐写项目.docx" --out teaching/web/zh --lang zh
	$(PY) teaching/web/docx2md.py --docx "thesis/Learning-Handbook-From-Zero-to-nsF5-Steganography.docx" --out teaching/web/en --lang en
	$(PY) teaching/web/add_lang_switch.py

web-build:
	jupyter-book build teaching/web/zh
	jupyter-book build teaching/web/en
