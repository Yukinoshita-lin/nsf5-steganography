FROM python:3.11-slim

LABEL org.opencontainers.image.title="nsf5stego-teaching"
LABEL org.opencontainers.image.description="Jupyter teaching environment for the nsF5 steganography project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Core pure-Python algorithm modules (C++ DLLs are Windows-only and left out;
# embed/decode falls back to the equivalent Python path automatically).
COPY pyproject.toml README.md ./
COPY src ./src
COPY notebooks ./notebooks
COPY scripts ./scripts
COPY teaching ./teaching

ENV PYTHONPATH=/workspace/src

RUN pip install --no-cache-dir \
        numpy pillow matplotlib scikit-learn joblib pandas \
        jupyterlab nbformat \
    && python -m compileall -q src teaching scripts \
    && python src/test_core.py \
    && python src/test_steg.py

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=nsf5"]
