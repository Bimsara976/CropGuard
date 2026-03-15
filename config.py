from dotenv import load_dotenv
load_dotenv()
#Handle Environment Variables

import os

# Get the base directory of the project for path joining
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── MongoDB Configuration ─────────────────────────────────────────────────────
# In Docker environments, MONGO_URI is typically set to "mongodb://mongo:27017/"
# If we're running locally for development, it defaults to localhost.
LOCAL_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME   = 'CropGuard'

# ── ML Model Files ────────────────────────────────────────────────────────────
# Paths to the saved Keras model and its metadata (class names, etc.)
MODEL_PATH    = os.path.join(BASE_DIR, 'model', 'ensemble_model.keras')
METADATA_PATH = os.path.join(BASE_DIR, 'model', 'model_metadata.json')

# ── Gemini API (Vision Backend) ───────────────────────────────────────────────
# We use Gemini as our fallback or primary inference engine.
# Make sure to set this in your .env file or environment variables.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ── Flask App Settings ────────────────────────────────────────────────────────
# Secret key for session signing - keep this safe in production!
SECRET_KEY         = os.environ.get('SECRET_KEY', 'cropguard-secret-key-w1953807-2025')
# Limit uploads to 10MB to prevent server strain
MAX_CONTENT_LENGTH = 10 * 1024 * 1024
# We only want to process these specific image formats
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# ── Inference Logic ───────────────────────────────────────────────────────────
# If the model's confidence is lower than this, we flag it as an uncertain result
CONFIDENCE_THRESHOLD = 0.30

# ── Image storage (resize before saving to MongoDB) ───────────────────────────
# We resize images before saving to the database to keep the DB size manageable
IMG_STORE_MAX_SIZE = (640, 640)
IMG_STORE_QUALITY  = 72   # JPEG quality percentage
