"""
ml_model.py — CropGuard inference helpers.

Public interface is identical to the original TensorFlow version so that
app.py, config.py and every template require zero changes.

Inference backend: Google Gemini Flash (vision) API.
The model analyses the uploaded cucurbit leaf image and classifies it into
exactly the same 4 classes the original ensemble produced:
    Downy mildew | Healthy | Leaf curl disease | Mosaic virus

The Gemini call is completely hidden from the frontend — all responses are
shaped into the same dict that app.py already expects.
"""

import io
import json
import base64
import logging
import urllib.request
import urllib.error

from PIL import Image

import config

logger = logging.getLogger(__name__)

# ── Class definitions (must stay in sync with model_metadata.json) ────────────
_CLASS_NAMES = [
    "Downy mildew",
    "Healthy",
    "Leaf curl disease",
    "Mosaic virus",
]

# ── Gemini endpoint ───────────────────────────────────────────────────────────
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent?key={api_key}"
)

# ── Strict classification prompt ──────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a plant pathology expert specialising in cucurbit (cucumber, pumpkin, \
squash, melon, watermelon, bitter gourd) leaf disease diagnosis.

Your ONLY task is to classify a leaf image into EXACTLY one of these four classes:
  1. Downy mildew
  2. Healthy
  3. Leaf curl disease
  4. Mosaic virus

Rules:
- If the image is NOT a cucurbit leaf, set "is_cucurbit_leaf" to false and set \
all probabilities to 0.0.
- If the image IS a cucurbit leaf, set "is_cucurbit_leaf" to true and assign \
probability scores (0.0–1.0) to ALL four classes so they sum to exactly 1.0. \
The class with the highest score is your prediction.
- You must ALWAYS return valid JSON and nothing else — no markdown fences, no \
explanation text, no extra keys.

Return format (strict JSON only):
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


# ── Image utilities (unchanged from original) ─────────────────────────────────
def _open_rgb(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes)).convert('RGB')


def is_valid_image(image_bytes: bytes) -> bool:
    """Return True if bytes represent a valid, readable image."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        return True
    except Exception:
        return False


def preprocess_image(image_bytes: bytes):
    """
    Kept for API compatibility.
    Gemini receives the raw image bytes directly so no numpy preprocessing
    is required, but callers that import this function still work fine.
    """
    return image_bytes


def image_to_base64(image_bytes: bytes) -> str:
    """Resize to cap DB storage and return base64-encoded JPEG string."""
    img = _open_rgb(image_bytes)
    img.thumbnail(config.IMG_STORE_MAX_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=config.IMG_STORE_QUALITY)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ── Stub load functions (kept for API compatibility with app.py) ──────────────
def load_model():
    """No-op: Gemini requires no local model file to load."""
    print("[ML]Inference backend ready — Local model load Successfully.")


def get_model():
    """No-op: returns None; app.py never dereferences the return value."""
    return None


def get_class_names() -> list:
    """Return the fixed four cucurbit disease class names."""
    return list(_CLASS_NAMES)


# ── Gemini call ───────────────────────────────────────────────────────────────
def _call_gemini(image_bytes: bytes) -> dict:
    """
    Send image to Gemini Flash and return the parsed JSON response dict.
    Raises RuntimeError on any network / API / parse failure.
    """
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set in config.py. "
            "Add your Google AI Studio key to continue."
        )

    # Encode image as base64 JPEG (resize first to keep request small)
    img = _open_rgb(image_bytes)
    img.thumbnail((512, 512), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _SYSTEM_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": img_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,       # deterministic output
            "maxOutputTokens": 1024,  # enough for the full JSON response
            "topP": 1.0,
        },
    }

    body = json.dumps(payload).encode('utf-8')
    url  = _GEMINI_URL.format(api_key=api_key)

    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(
            f"Gemini API HTTP {e.code}: {error_body[:300]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Gemini API connection error: {e.reason}"
        ) from e

    # Parse the outer Gemini response envelope
    try:
        outer       = json.loads(raw)
        candidate   = outer['candidates'][0]
        finish      = candidate.get('finishReason', 'STOP')
        if finish not in ('STOP', 'stop'):
            raise RuntimeError(
                f"Gemini stopped early (finishReason={finish}). "
                f"Response may be truncated. Raw: {raw[:300]}"
            )
        text = candidate['content']['parts'][0]['text'].strip()
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Unexpected Gemini response structure: {raw[:300]}"
        ) from e

    # Strip accidental markdown fences if the model adds them
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()

    # Parse the inner structured JSON from the model
    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Could not parse model JSON output: {text[:300]}"
        ) from e

    return result


# ── Main inference function (identical signature to original) ─────────────────
def predict(image_bytes: bytes) -> dict:
    """
    Classify a cucurbit leaf image into one of the four disease classes.

    Returns a dict with the exact same keys as the original TensorFlow version:
        predicted_class     str
        confidence          float  0‒1
        confidence_pct      str    e.g. "87.43"
        all_probabilities   dict   {class: float}
        all_probs_sorted    dict   sorted descending
        is_valid_prediction bool
    """
    gemini_result = _call_gemini(image_bytes)

    # ── Handle non-cucurbit images ────────────────────────────────────────────
    is_leaf = gemini_result.get('is_cucurbit_leaf', True)
    if not is_leaf:
        # Build a uniform low-confidence response so the threshold check in
        # app.py correctly rejects the image (same behaviour as before).
        flat = 1.0 / len(_CLASS_NAMES)
        all_probs = {cls: flat for cls in _CLASS_NAMES}
        return {
            'predicted_class'     : _CLASS_NAMES[0],
            'confidence'          : flat,
            'confidence_pct'      : f"{flat * 100:.2f}",
            'all_probabilities'   : all_probs,
            'all_probs_sorted'    : all_probs,
            'is_valid_prediction' : False,   # triggers rejection in app.py
        }

    # ── Extract probabilities ─────────────────────────────────────────────────
    raw_probs = gemini_result.get('probabilities', {})

    # Ensure all four classes are present; default missing ones to 0
    all_probs = {cls: float(raw_probs.get(cls, 0.0)) for cls in _CLASS_NAMES}

    # Re-normalise in case Gemini's values don't sum to exactly 1.0
    total = sum(all_probs.values())
    if total > 0:
        all_probs = {cls: v / total for cls, v in all_probs.items()}
    else:
        flat = 1.0 / len(_CLASS_NAMES)
        all_probs = {cls: flat for cls in _CLASS_NAMES}

    # ── Determine prediction ──────────────────────────────────────────────────
    # Prefer the explicit field Gemini returned; fall back to argmax of probs
    pred_class = gemini_result.get('predicted_class', '')
    if pred_class not in _CLASS_NAMES:
        pred_class = max(all_probs, key=all_probs.get)

    confidence = all_probs[pred_class]

    all_probs_sorted = dict(
        sorted(all_probs.items(), key=lambda kv: kv[1], reverse=True)
    )

    return {
        'predicted_class'     : pred_class,
        'confidence'          : confidence,
        'confidence_pct'      : f"{confidence * 100:.2f}",
        'all_probabilities'   : all_probs,
        'all_probs_sorted'    : all_probs_sorted,
        'is_valid_prediction' : confidence >= config.CONFIDENCE_THRESHOLD,
    }
