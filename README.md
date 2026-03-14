# 🌿 CropGuard — Cucurbit Disease Detection System

> Copyright © U.J Tharushi Thathsarani w1953807 2025-2026

CropGuard is an intelligent cucurbit leaf disease detection web application. Upload or capture a leaf image and receive an instant AI-powered disease classification along with expert treatment recommendations.

**Detectable conditions:** Downy Mildew · Leaf Curl Disease · Mosaic Virus · Healthy

---

## 🐳 Running with Docker (Recommended)

This is the easiest way to run CropGuard — no Python, no MongoDB, no manual setup required.

### Prerequisites

Install **Docker Desktop** on your machine:
- Windows / Mac: https://www.docker.com/products/docker-desktop
- Linux: https://docs.docker.com/engine/install/

Verify installation:
```bash
docker --version
docker compose version
```

---

### Step 1 — Get the project files

Either clone the repository or extract the zip file:
```bash
# Option A: Git clone
git clone <repository-url>
cd CropGuard

# Option B: Extract zip, then open terminal in the folder
```

---

### Step 2 — Add your model files

Place your model files in the `model/` folder:
```
CropGuard/
└── model/
    ├── ensemble_model.keras     ← your trained model
    └── model_metadata.json      ← class names and metadata
```

---

### Step 3 — Set your Gemini API key

Copy the example environment file and fill in your key:
```bash
# Windows (Command Prompt)
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Then open `.env` and replace `YOUR_GEMINI_API_KEY_HERE` with your actual key:
```
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Get a free key at: https://aistudio.google.com/app/apikey

---

### Step 4 — Build and start

```bash
docker compose up --build
```

First build takes 3–5 minutes (downloads Python, installs packages). Subsequent starts are instant.

Open your browser at: **http://localhost:5000**

---

### Common commands

```bash
# Start in background (detached mode)
docker compose up -d --build

# View live logs
docker compose logs -f

# Stop everything
docker compose down

# Stop and delete all data (MongoDB included)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

---

## 📁 Project Structure

```
CropGuard/
├── app.py                  # Flask routes
├── config.py               # Configuration (reads from env vars)
├── database.py             # MongoDB connection manager
├── ml_model.py             # Gemini API inference backend
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build instructions
├── docker-compose.yml      # Multi-service orchestration
├── .env.example            # Environment variable template
├── .env                    # Your secrets (never commit this)
├── .dockerignore           # Files excluded from Docker image
├── .gitignore              # Files excluded from Git
├── model/                  # ML model files (not in Git)
│   ├── ensemble_model.keras
│   └── model_metadata.json
├── mongo-init/             # MongoDB seed scripts
│   └── 01_seed_treatments.js
├── static/
│   ├── css/style.css
│   └── js/main.js
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── farmer_dashboard.html
    ├── agronomist_dashboard.html
    ├── upload.html
    ├── result.html
    └── history.html
```

---

## 🔧 Configuration

All settings are controlled via environment variables in your `.env` file:

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key | *(required)* |
| `SECRET_KEY` | Flask session secret | built-in default |
| `MONGO_URI` | MongoDB connection string | `mongodb://mongo:27017/` |

---

## 👤 User Roles

| Feature | Farmer | Agronomist |
|---|---|---|
| Upload & analyse leaf | ✅ | ✅ |
| DroidCam live capture | ✅ | ✅ |
| Disease name + treatment | ✅ | ✅ |
| Confidence percentage | ❌ | ✅ |
| Full probability matrix | ❌ | ✅ |
| Disease frequency stats | ❌ | ✅ |
| Export CSV / JSON | ✅ | ✅ |

---

## 📱 DroidCam Setup

To capture leaf images directly from your smartphone:

1. Install **DroidCam** on your Android or iOS device (free)
2. Connect your phone and PC to the **same Wi-Fi network**
3. Open DroidCam on your phone — note the IP address shown (e.g. `192.168.1.5`)
4. In CropGuard, go to **Analyse Leaf → DroidCam Capture**
5. Enter `http://192.168.1.5:4747/video` and click **Connect**
6. Point camera at the leaf → click **Capture Frame** → **Detect Disease**

---

## 🛠️ Local Development (without Docker)

```bash
# Create virtual environment
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
set GEMINI_API_KEY=your_key_here        # Windows
export GEMINI_API_KEY=your_key_here     # Mac/Linux

# Run
python app.py
```

Requires MongoDB running locally on port 27017.

---

## ⚠️ Notes

- The `.env` file contains your API key — **never share or commit it**
- MongoDB data is stored in a Docker named volume (`cropguard_mongo_data`) and persists across restarts
- Run `docker compose down -v` only if you want to completely wipe the database
- The app uses 1 Gunicorn worker + 4 threads — this is intentional for thread-safe Gemini inference
