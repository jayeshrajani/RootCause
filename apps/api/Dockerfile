FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Reference retrieval (DINOv2 + FAISS). CPU-only torch: the default Linux wheel bundles CUDA (GBs).
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install ".[retrieval]"

RUN useradd --system --uid 10001 rootcause
USER rootcause

# Cloud Run injects PORT; 8080 is the local default. Model weights and the FAISS index are mounted
# read-only at ROOTCAUSE_DATA_DIR (see deploy/README.md); retrieval stays off until
# ROOTCAUSE_RETRIEVAL_INDEX_VERSION is set.
ENV PORT=8080 ROOTCAUSE_ENVIRONMENT=production \
    OMP_NUM_THREADS=2 HF_HOME=/tmp/huggingface
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
