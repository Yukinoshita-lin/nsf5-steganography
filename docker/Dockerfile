FROM python:3.11-slim

LABEL org.opencontainers.image.title="nsf5stego-teaching"
LABEL org.opencontainers.image.description="Jupyter teaching environment for the nsF5 steganography project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# libgomp1: lightgbm 的 manylinux wheel 链接 OpenMP 运行时, 而 slim 镜像不带它。
# 缺了会在 `joblib.load` 两个部署模型时抛 OSError: libgomp.so.1: cannot open
# shared object file —— 表现为"模型未能加载", 而不是一句能指向根因的报错。

# Core pure-Python algorithm modules. The C++ accelerators are not built here:
# they are optional, so embed/decode and feature extraction fall back to the
# equivalent pure-Python paths automatically (build them with `make cpp` if you
# want the speedup in a derived image).
COPY pyproject.toml README.md ./
COPY src ./src
COPY notebooks ./notebooks
COPY scripts ./scripts
COPY teaching ./teaching
# The two deployable models ship with the repo, so the image carries them too:
# without models/ *and* lightgbm, MLPredictor silently reports available=False
# and every ML cell in the notebooks would dead-end.
COPY models ./models

ENV PYTHONPATH=/workspace/src

RUN pip install --no-cache-dir \
        numpy pillow matplotlib scikit-learn joblib pandas lightgbm \
        jupyterlab nbformat \
    && python -m compileall -q src teaching scripts \
    && python src/test_core.py \
    && python src/test_steg.py \
    && python src/test_pipeline.py

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=nsf5"]
