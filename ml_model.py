"""
ml_model.py — CropGuard inference helpers.
We've replaced the local TensorFlow ensemble with the Google Gemini Flash API.
This allows us to maintain the same public interface so the rest of the app 
doesn't even know the backend changed.
"""

import io
import json
import base64
import logging
import urllib.request
import urllib.error

from PIL import Image
import config

# Standard logger setup for tracking issues
logger = logging.getLogger(__name__)

# Class labels for our diseases. MUST match what the frontend expects.
_CLASS_NAMES = [
    "Downy mildew",
    "Healthy",
    "Leaf curl disease",
    "Mosaic virus",
]

# API endpoint for the Gemini vision model
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent?key={api_key}"
)

# This is the "brain" of our AI. We tell Gemini exactly how to behave.
# We demand JSON so we can parse it programmatically.
_SYSTEM_PROMPT = """\
You are a plant pathology expert specialising in cucurbit (cucumber, pumpkin, \
squash, melon, watermelon, bitter gourd) leaf disease diagnosis.

Your ONLY task is to classify a leaf image into EXACTLY one of these four classes:
  1. Downy mildew
  2. Healthy
  3. Leaf curl disease
  4. Mosaic virus

Rules:
- If the image is NOT a cucurbit leaf, set "is_cucurbit_leaf" to false.
- If it IS a cucurbit leaf, assign probabilities (0-1) to all four classes summing to 1.0.
- ALWAYS return valid JSON. No conversational text or markdown fences.

Return format:
{
  "is_cucurbit_leaf": true,
  "predicted_class": "<one of the four class names>",
  "probabilities": {
    "Downy mildew": 0.0,
    "Healthy": 0.0,
    "Leaf curl disease": 0.0,
    "Mosaic virus": 0.0
  }
}
"""


# ── Image processing helpers ──────────────────────────────────────────────────
def _open_rgb(image_bytes: bytes) -> Image.Image:
    """Helper to open bytes as a PIL Image in RGB mode."""
    return Image.open(io.BytesIO(image_bytes)).convert('RGB')


def is_valid_image(image_bytes: bytes) -> bool:
    """Verifies if the uploaded bytes are actually a readable image."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        return True
    except Exception:
        return False


def preprocess_image(image_bytes: bytes):
    """
    Left here for compatibility with the old app code. 
    Gemini handles raw bytes, so we just pass them through.
    """
    return image_bytes


def image_to_base64(image_bytes: bytes) -> str:
    """
    Prepares the image for MongoDB storage by resizing and encoding as base64.
    This saves space and allows easy rendering in HTML templates.
    """
    img = _open_rgb(image_bytes)
    img.thumbnail(config.IMG_STORE_MAX_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=config.IMG_STORE_QUALITY)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ── API compatibility stubs ───────────────────────────────────────────────────
def load_model():
    """No-op: Since we use Gemini, there's no local .keras file to load into memory."""
    print("[ML] Inference backend (Gemini) ready.")


def get_model():
    """The app expects a model object, but Gemini is an API. Returning None works fine."""
    return None


def get_class_names() -> list:
    """Public helper to get the disease labels used throughout the project."""
    return list(_CLASS_NAMES)


# ── The core Gemini API call ──────────────────────────────────────────────────
def _call_gemini(image_bytes: bytes) -> dict:
    """
    Sends the image to Google AI Studio and parses the response.
    Includes error handling for network issues or API failures.
    """
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Check your configuration.")

    # We resize the image for the API call to speed up the upload
    img = _open_rgb(image_bytes)
    img.thumbnail((512, 512), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    # Construct the JSON payload for the Gemini API
    payload = {
        "contents": [{
            "parts": [
                {"text": _SYSTEM_PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.0, # Deterministic: same image = same result
            "maxOutputTokens": 1024,
            "topP": 1.0,
        },
    }

    body = json.dumps(payload).encode('utf-8')
    url  = _GEMINI_URL.format(api_key=api_key)
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"Gemini API request failed: {e}")

    # Parse the response and dig out the text content
    try:
        outer = json.loads(raw)
        text = outer['candidates'][0]['content']['parts'][0]['text'].strip()
    except (KeyError, IndexError, json.JSONDecodeError):
        raise RuntimeError("Failed to parse response from Gemini API.")

    # Sometimes LLMs add markdown fences (```json ... ```). We strip those.
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'): text = text[4:]
        text = text.strip()

    return json.loads(text)


def predict(image_bytes: bytes) -> dict:
    """
    Takes raw image bytes and returns a structured prediction dictionary.
    Handles non-leaf images and normalizes confidence scores.
    """
    try:
        gemini_result = _call_gemini(image_bytes)
    except Exception as e:
        # If the API fails, we need to report it gracefully
        raise RuntimeError(f"Prediction failed: {e}")

    # Check if the AI actually thinks this is a cucurbit leaf
    is_leaf = gemini_result.get('is_cucurbit_leaf', True)
    if not is_leaf:
        # Fallback for irrelevant images
        flat = 1.0 / len(_CLASS_NAMES)
        all_probs = {cls: flat for cls in _CLASS_NAMES}
        return {
            'predicted_class'     : _CLASS_NAMES[0],
            'confidence'          : flat,
            'confidence_pct'      : "0.00",
            'all_probabilities'   : all_probs,
            'all_probs_sorted'    : all_probs,
            'is_valid_prediction' : False,
        }

    # Normalize the probabilities returned by Gemini
    raw_probs = gemini_result.get('probabilities', {})
    all_probs = {cls: float(raw_probs.get(cls, 0.0)) for cls in _CLASS_NAMES}
    
    total = sum(all_probs.values())
    if total > 0:
        all_probs = {cls: v / total for cls, v in all_probs.items()}
    else:
        all_probs = {cls: 0.25 for cls in _CLASS_NAMES}

    # Decide on the final prediction
    pred_class = gemini_result.get('predicted_class', '')
    if pred_class not in _CLASS_NAMES:
        pred_class = max(all_probs, key=all_probs.get)

    confidence = all_probs[pred_class]
    all_probs_sorted = dict(sorted(all_probs.items(), key=lambda kv: kv[1], reverse=True))

    return {
        'predicted_class'     : pred_class,
        'confidence'          : confidence,
        'confidence_pct'      : f"{confidence * 100:.2f}",
        'all_probabilities'   : all_probs,
        'all_probs_sorted'    : all_probs_sorted,
        'is_valid_prediction' : confidence >= config.CONFIDENCE_THRESHOLD,
    }
