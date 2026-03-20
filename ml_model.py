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
You are a specialist plant pathologist with deep expertise in cucurbit \
(cucumber, pumpkin, squash, melon, watermelon, bitter gourd) leaf diseases. \
You are highly skilled at distinguishing visually similar diseases.

Your ONLY task is to classify the provided leaf image into EXACTLY one of \
these four classes. Study the image carefully before deciding.

════════════════════════════════════════════════════════
VISUAL DIAGNOSTIC GUIDE — READ CAREFULLY BEFORE CLASSIFYING
════════════════════════════════════════════════════════

1. DOWNY MILDEW
   PRIMARY SIGNS (must have at least one):
   - Angular yellow or pale-green patches on the UPPER leaf surface, strictly
     bounded by the leaf veins (giving a geometric, blocky pattern)
   - Grey, purple, or white fuzzy/downy sporulation on the LOWER leaf surface
     directly beneath the yellow patches
   OTHER SIGNS: Affected areas eventually turn brown and papery. No major leaf
   deformation or curl. Colour change is the dominant symptom.
   KEY DISTINCTION: Bounded angular yellow patches + underside sporulation.
     No mosaic/mottling pattern. No severe curling.

2. HEALTHY
   SIGNS: Uniform green colour across the entire leaf. Smooth, flat surface.
     No discolouration, spots, patches, distortion, curling, or mottling.
   KEY DISTINCTION: Completely uniform green. Any abnormality rules this out.

3. LEAF CURL DISEASE  ← FOCUS CAREFULLY ON THIS CLASS
   PRIMARY SIGNS (must have at least one):
   - Leaves are SEVERELY CURLED or CUPPED upward or downward — the curl is
     the most prominent feature, not colour change
   - Leaves appear CRINKLED, RUGOSE (bumpy/blistered texture), or puckered
   - Leaf edges roll inward or upward tightly
   - Stunted, thickened, leathery leaf texture
   - Young leaves are often very small, distorted and cup-shaped
   COLOUR: May show mild yellowing or slight mosaic BUT the DOMINANT symptom
     is the PHYSICAL DEFORMATION (curling/crinkling), not the colour pattern
   KEY DISTINCTION vs Mosaic Virus:
     → Leaf Curl = STRUCTURAL deformation is dominant (curled, cupped, rugose)
     → Mosaic    = COLOUR pattern is dominant (mottled, flat leaf)
     If the leaf is SEVERELY CURLED or CRINKLED → classify as Leaf curl disease

4. MOSAIC VIRUS
   PRIMARY SIGNS (must have at least one):
   - Clear alternating light-green and dark-green MOSAIC or MOTTLING colour
     pattern across the leaf surface
   - Irregular yellow/green patches in a mosaic pattern
   - Leaf surface is RELATIVELY FLAT — minimal physical deformation
   - Blistering or puckering may be mild, but colour contrast is dominant
   COLOUR: Strong visual contrast between light and dark green areas is key
   KEY DISTINCTION vs Leaf Curl Disease:
     → Mosaic = Leaf is mostly FLAT with a MOTTLED COLOUR PATTERN
     → Leaf Curl = Leaf is PHYSICALLY DEFORMED (curled/rugose) regardless of colour

════════════════════════════════════════════════════════
CLASSIFICATION RULES
════════════════════════════════════════════════════════
- If the leaf is NOT a cucurbit leaf, set "is_cucurbit_leaf" to false.
- If it IS a cucurbit leaf, assign probabilities (0.0–1.0) to ALL four classes
  that sum to exactly 1.0.
- The "predicted_class" MUST be the class with the highest probability.
- If the leaf shows BOTH curling AND mosaic colouring, prioritise the DOMINANT
  visual feature: severe curl → Leaf curl disease; flat + colour pattern → Mosaic virus.
- ALWAYS return valid JSON only. No markdown fences, no explanatory text.

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
    req  = urllib.request.Request(
        url, data=body,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    # ── Network call with up to 2 retries ─────────────────────────────────────
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8')
            break
        except Exception as e:
            last_err = e
            logger.warning(f"[Gemini] Attempt {attempt + 1} failed: {e}")
    else:
        raise RuntimeError(f"Gemini API request failed after 3 attempts: {last_err}")

    # ── Extract the text field from the Gemini response envelope ─────────────
    try:
        outer = json.loads(raw)
        text  = outer['candidates'][0]['content']['parts'][0]['text'].strip()
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Unexpected Gemini response structure: {e}")

    # ── Clean the text so it's valid JSON ─────────────────────────────────────
    text = _clean_gemini_text(text)

    # ── Parse with fallback reconstruction on failure ─────────────────────────
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"[Gemini] JSON parse failed ({e}), attempting recovery on: {text[:200]}")
        recovered = _recover_json(text)
        if recovered:
            return recovered
        raise RuntimeError(
            f"Could not parse Gemini response as JSON. "
            f"Parse error: {e}. Raw text (first 300 chars): {text[:300]}"
        )


def _clean_gemini_text(text: str) -> str:
    """
    Strips all the ways Gemini wraps its JSON response in extra text.
    Handles markdown fences, leading prose, trailing comments, and
    Unicode control characters that break the JSON parser.
    """
    import re

    # 1. Strip markdown code fences  (```json ... ``` or ``` ... ```)
    #    Handle both cases where the fence is at the start or mid-text
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    elif text.startswith('```'):
        # Malformed fence with no closing — strip the opening tag
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE).strip()

    # 2. Extract the first {...} block in case Gemini adds prose before/after
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        text = brace_match.group(0).strip()

    # 3. Remove trailing commas before } or ] (common LLM mistake)
    #    e.g.  "Mosaic virus": 0.05,\n}  →  "Mosaic virus": 0.05\n}
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # 4. Remove JavaScript-style single-line comments  // ...
    text = re.sub(r'//[^\n]*', '', text)

    # 5. Remove Unicode control / zero-width characters that break the parser
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove the Unicode "double-struck" box characters used in the prompt
    # (════) which occasionally leak into the model output
    text = re.sub(r'[^\x00-\x7f]', lambda m: m.group(0) if m.group(0) in '""''…' else
                  (m.group(0) if ord(m.group(0)) > 127 and m.group(0).isprintable() else ''), text)

    # 6. Fix curly/smart quotes that some locales substitute for straight quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')  # " "
    text = text.replace('\u2018', "'").replace('\u2019', "'")  # ' '

    return text.strip()


def _recover_json(text: str) -> dict | None:
    """
    Last-resort recovery: if the JSON is still broken after cleaning,
    attempt to reconstruct a valid response by regex-extracting the key fields.
    Returns a valid dict or None if recovery is impossible.
    """
    import re

    try:
        # Try to find is_cucurbit_leaf
        leaf_match = re.search(r'"is_cucurbit_leaf"\s*:\s*(true|false)', text, re.IGNORECASE)
        is_leaf = (leaf_match.group(1).lower() == 'true') if leaf_match else True

        # Try to find predicted_class
        class_match = re.search(r'"predicted_class"\s*:\s*"([^"]+)"', text)
        pred_class  = class_match.group(1) if class_match else None

        # Try to extract individual probabilities
        probs = {}
        for cls in _CLASS_NAMES:
            pattern = rf'"{re.escape(cls)}"\s*:\s*([0-9]*\.?[0-9]+)'
            m = re.search(pattern, text, re.IGNORECASE)
            probs[cls] = float(m.group(1)) if m else 0.0

        # Validate we got something useful
        if pred_class not in _CLASS_NAMES:
            # Fall back to whichever class has the highest extracted probability
            if any(v > 0 for v in probs.values()):
                pred_class = max(probs, key=probs.get)
            else:
                return None  # Nothing usable recovered

        logger.info(f"[Gemini] JSON recovered via regex. predicted_class={pred_class}")
        return {
            'is_cucurbit_leaf': is_leaf,
            'predicted_class' : pred_class,
            'probabilities'   : probs,
        }

    except Exception as e:
        logger.error(f"[Gemini] Recovery also failed: {e}")
        return None


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
