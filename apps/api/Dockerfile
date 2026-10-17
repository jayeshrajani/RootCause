FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
# FAISS only: reference photos are embedded with Gemini, so torch/DINOv2 are not needed here.
RUN pip install ".[index]"

RUN useradd --system --uid 10001 rootcause
USER rootcause

# Cloud Run injects PORT; 8080 is the local default.
ENV PORT=8080 ROOTCAUSE_ENVIRONMENT=production
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
