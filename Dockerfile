# ─────────────────────────────────────────────────────────────────────────────
# CropGuard — Dockerfile
# Copyright U.J Tharushi Thathsarani w1953807 2025-2026
#
# Build:  docker compose up --build
# ─────────────────────────────────────────────────────────────────────────────

# Use the official slim Python 3.11 image (matches your dev environment)
FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# libgomp1  : required by TensorFlow (OpenMP runtime)
# libglib2-0: required by Pillow on some platforms
# curl      : used by the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first so Docker layer cache skips re-install on code changes
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# ── Runtime environment variables ─────────────────────────────────────────────
# These are defaults; override them in docker-compose.yml or with -e flags.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    TF_CPP_MIN_LOG_LEVEL=2 \
    TF_ENABLE_ONEDNN_OPTS=0 \
    CUDA_VISIBLE_DEVICES=-1

# ── Expose Flask port ─────────────────────────────────────────────────────────
EXPOSE 5000

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# ── Start with Gunicorn (production WSGI server) ──────────────────────────────
# Workers: 1 — TensorFlow/Gemini inference is not safe with multiple workers
#              sharing the same process space. Use 1 worker + threads instead.
CMD ["python", "-m", "gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
