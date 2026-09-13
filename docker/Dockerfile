FROM python:3.11-slim

LABEL org.opencontainers.image.title="nsf5stego-teaching"
LABEL org.opencontainers.image.description="Jupyter teaching environment for the nsF5 steganography project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

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
