import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── MongoDB ──────────────────────────────────────────────────────────────────
# Using local database only
LOCAL_URI = "mongodb://localhost:27017/"
DB_NAME   = "CropGuard"

# ── ML Model ─────────────────────────────────────────────────────────────────
MODEL_PATH    = os.path.join(BASE_DIR, 'model', 'ensemble_model.keras')
METADATA_PATH = os.path.join(BASE_DIR, 'model', 'model_metadata.json')
GEMINI_API_KEY = 'AIzaSyC4HeCm-KwLov8Z1VLgu5XVBoNSexcxE-0'

# ── Flask ─────────────────────────────────────────────────────────────────────
SECRET_KEY          = 'cropguard-secret-key-w1953807-2025'
MAX_CONTENT_LENGTH  = 10 * 1024 * 1024   # 10 MB upload limit
ALLOWED_EXTENSIONS  = {'jpg', 'jpeg', 'png'}

# ── Inference ─────────────────────────────────────────────────────────────────
# If max class confidence is below this value, image is rejected as non-related.
# The ensemble is a closed-set 4-class classifier with no "unknown" class, so
# even a healthy cucurbit leaf may score 30-45% on its top class when disease
# probabilities are spread across several candidates.  A threshold of 0.30
# reliably rejects truly unrelated images (which score ~25% per class) while
# accepting real cucurbit leaf photos.
CONFIDENCE_THRESHOLD = 0.30

# ── Image storage (resize before saving to MongoDB) ───────────────────────────
IMG_STORE_MAX_SIZE = (640, 640)
IMG_STORE_QUALITY  = 72   # JPEG quality %
