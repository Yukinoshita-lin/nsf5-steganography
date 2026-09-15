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
	e2e gui notebooks dataset docker web-convert web-build exp-data exp-figs \
	exp-models results results-check ood gain-importance handbook-check handbook-fix \
	notebooks-run hooks attribution-check handbook-snippets coverage \
	model-cards model-cards-check handbook-pdf

help:
	@echo "Targets:"
	@echo "  make install      - editable install (uses $(PY))"
	@echo "  make test         - core + steganalysis + false-positive + features"
	@echo "  make pytest       - run the whole suite through pytest"
	@echo "  make cpp          - build the C++ accelerators into cpp/ (optional)"
	@echo "  make exp-figs     - rebuild experiment figures from experiments/data/*.csv"
	@echo "  make exp-models   - retrain the two deployed models (reproducible producer)"
	@echo "  make model-cards  - regenerate models/*.card.json (model cards)"
	@echo "  make model-cards-check - verify model cards match the .joblib binaries (CI uses this)"
	@echo "  make results      - rebuild docs/RESULTS.md (canonical results table)"
	@echo "  make results-check - verify docs/RESULTS.md is in sync"
	@echo "  make ood          - OOD real-photo false-positive evaluation (1514 photos)"
	@echo "  make gain-importance - regenerate LGB gain importance tables"
	@echo "  make handbook-check- verify handbooks carry no stale claims (CI uses this)"
	@echo "  make handbook-fix - correct the handbook sources (DOCX + web) from the fact table"
	@echo "  make notebooks-run - execute all 10 teaching notebooks headlessly"
	@echo "  make hooks        - enable the repo git hooks (.githooks, strips AI co-author trailers)"
	@echo "  make attribution-check - verify no AI co-author trailer in history"
	@echo "  make handbook-snippets - execute the python code blocks in the handbook"
	@echo "  make handbook-pdf - re-export docs/*.pdf from the DOCX sources (needs Word)"
	@echo "  make coverage     - full suite with coverage report"
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

# 论文实验: 脚本入库 (experiments/), 数据与图是产物 (experiments/{data,figs},
# 已被 .gitignore 忽略)。
#   先出数据(含 CNN 训练, 约 2 小时), 再出图。
#   只要已有 experiments/data/*.csv, 单独跑 `make exp-figs` 即可。
# CNN 本体在 gpu/train_cnn.py; 这里只是编排与出图。
exp-figs:
	$(PY) experiments/gen_figs.py

exp-data:
	$(PY) experiments/featurize_bossbase_npz.py
	$(PY) experiments/run_cnn_sota.py
	$(PY) experiments/eval_cnn_checkpoint.py
	$(PY) experiments/sota_compare.py
	$(PY) experiments/merge_sota_table.py

# 两个部署模型的生产者 (校园语料, 不需要 GPU/torch)。产出的 .joblib 会被覆盖,
# 指标落在 experiments/data/deploy_model_metrics.csv。
exp-models:
	$(PY) experiments/train_deploy_models.py

# 部署模型卡 (models/*.card.json): 语料/协议/指标/特征顺序/适用边界 + sha256。
# 校验失败几乎总是意味着 .joblib 换了而卡没重生成 —— 先跑 exp-models。
model-cards:
	$(PY) experiments/model_card.py

model-cards-check:
	$(PY) experiments/model_card.py --check

# 唯一权威结果表: 合并所有实验产物, 逐行标注语料/协议/可溯源性。
results:
	$(PY) experiments/build_results_table.py

results-check:
	$(PY) experiments/build_results_table.py --check

# OOD 真实干净照片误报率 (需要 data/external/{div2k,alaska2}, 见 experiments/README.md)
ood:
	$(PY) experiments/ood_eval.py

# 特征重要性 (LightGBM gain) 的生产者
gain-importance:
	$(PY) experiments/gain_importance.py

# 手册事实校验/修正: 陈旧结论必须消失, 现口径必须出现 (见 teaching/handbook_facts.py)
handbook-check:
	$(PY) teaching/handbook_facts.py --check

handbook-fix:
	$(PY) teaching/handbook_facts.py --fix --web

# 逐个执行教学 notebook (CI 与本地共用)
notebooks-run:
	$(PY) teaching/run_notebooks.py --timeout 900

# 启用仓库自带 git 钩子: 提交时自动剔除 AI 协作工具的署名尾注
hooks:
	git config core.hooksPath .githooks
	@echo "hooks enabled: core.hooksPath=.githooks (commit-msg 会剔除 AI 尾注)"

# 兜底检查: 历史(或某次提交)里是否残留 AI 共同作者尾注
attribution-check:
	@git log --format=%B | grep -Eiq '^Co-Authored-By:.*(anthropic|openai|claude|codex|copilot|trae)' \
		&& { echo "发现 AI 共同作者尾注"; exit 1; } || echo "历史干净: 无 AI 共同作者尾注"

# 手册里的 python 片段必须真的能跑 (可执行片段全部执行, 例外见脚本里的清单)
handbook-snippets:
	$(PY) teaching/verify_handbook_experiments.py

# 入库 PDF 由 DOCX 导出 (Word COM)。Word 不在时脚本会明确跳过并返回 0,
# 所以在 Linux/CI 上调它也安全。
handbook-pdf:
	$(PY) teaching/export_handbook_pdf_word.py

# 带覆盖率的完整测试 (门槛见 pyproject / CI)
coverage:
	$(PY) -m pytest -q --cov --cov-report=term

docker:
	docker compose up --build

web-convert:
	$(PY) teaching/web/docx2md.py --docx "docs/src/学习手册-从零读懂nsF5隐写项目.docx" --out teaching/web/zh --lang zh
	$(PY) teaching/web/docx2md.py --docx "docs/src/Learning-Handbook-From-Zero-to-nsF5-Steganography.docx" --out teaching/web/en --lang en
	$(PY) teaching/web/add_lang_switch.py

web-build:
	jupyter-book build teaching/web/zh
	jupyter-book build teaching/web/en
