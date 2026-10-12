# ============================================================
# BASE IMAGE
# ============================================================
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ============================================================
# SYSTEM PACKAGES (OCR: TESSERACT + POPPLER)
# ============================================================
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# PYTHON DEPENDENCIES
# ============================================================
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# ============================================================
# APPLICATION CODE
# ============================================================
COPY app ./app

# Uploaded files are written here; run as a non-root user.
RUN useradd --create-home appuser \
    && mkdir -p uploads \
    && chown -R appuser:appuser /app

USER appuser

# ============================================================
# START THE API
# Hosting platforms (Render, Railway, Fly) provide $PORT.
# ============================================================
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
