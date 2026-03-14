import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── MongoDB ───────────────────────────────────────────────────────────────────
# In Docker, MONGO_URI is set to "mongodb://mongo:27017/" (service name).
# Outside Docker (local dev), it falls back to localhost.
LOCAL_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME   = 'CropGuard'

# ── ML Model ──────────────────────────────────────────────────────────────────
MODEL_PATH    = os.path.join(BASE_DIR, 'model', 'ensemble_model.keras')
METADATA_PATH = os.path.join(BASE_DIR, 'model', 'model_metadata.json')

# ── Gemini API ────────────────────────────────────────────────────────────────
# Set via environment variable — never hard-code in source.
# Docker: set in docker-compose.yml environment section or .env file.
# Local:  set in your shell or paste directly here for quick testing only.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ── Flask ─────────────────────────────────────────────────────────────────────
SECRET_KEY         = os.environ.get('SECRET_KEY', 'cropguard-secret-key-w1953807-2025')
MAX_CONTENT_LENGTH = 10 * 1024 * 1024   # 10 MB upload limit
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# ── Inference ─────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.30

# ── Image storage (resize before saving to MongoDB) ───────────────────────────
IMG_STORE_MAX_SIZE = (640, 640)
IMG_STORE_QUALITY  = 72   # JPEG quality %
