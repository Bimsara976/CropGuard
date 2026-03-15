"""
app.py — CropGuard Flask Application v2.0
This is the main entry point for the web application. It handles routing,
user authentication, image uploads, and connects the frontend to the ML backend.
"""

import csv
import io
import json
from datetime import datetime
from functools import wraps

import bcrypt
from bson import ObjectId
from flask import (Flask, Response, flash, redirect, render_template,
                   request, session, url_for)

import config
import ml_model
from database import get_db, get_connection_type

# ── App initialisation ────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key              = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH


# ── Decorators (Auth Guards) ──────────────────────────────────────────────────
def login_required(f):
    """Ensures that a user is logged in before accessing a route."""
    @wraps(f)
    def _inner(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return _inner


def role_required(*roles):
    """Restricts access based on user roles (e.g., 'farmer' or 'agronomist')."""
    def decorator(f):
        @wraps(f)
        def _inner(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return _inner
    return decorator


# ── Internal Helpers ──────────────────────────────────────────────────────────
def _allowed_file(filename: str) -> bool:
    """Checks if the uploaded file has a supported extension."""
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS)


def _format_predictions(preds: list) -> list:
    """Prepare database records for the frontend by formatting dates and IDs."""
    for p in preds:
        p['_id'] = str(p['_id'])
        p['date'] = (p['created_at'].strftime('%Y-%m-%d %H:%M')
                     if p.get('created_at') else 'N/A')
    return preds


def _build_stats(db, username: str) -> dict:
    """Calculates total scans and disease distribution for a specific user."""
    total = db.predictions.count_documents({'username': username})
    disease_counts = {}
    for cls in ml_model.get_class_names():
        disease_counts[cls] = db.predictions.count_documents(
            {'username': username, 'predicted_class': cls}
        )
    return {'total': total, 'disease_counts': disease_counts}


# ── Public Routes ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    """Home page. If already logged in, skip directly to the dashboard."""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user sign-ups with basic validation and password hashing."""
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Grab data from form and clean it up
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', '').lower()

        # Run some simple checks to ensure data quality
        errors = []
        if not username: errors.append('Username is required.')
        if not password: errors.append('Password is required.')
        if len(username) < 3: errors.append('Username must be at least 3 characters.')
        if len(password) < 6: errors.append('Password must be at least 6 characters.')
        if password != confirm: errors.append('Passwords do not match.')
        if role not in ('farmer', 'agronomist'): errors.append('Please select a valid role.')

        if errors:
            for e in errors: flash(e, 'danger')
            return render_template('register.html', form_data={'username': username, 'role': role})

        db, _ = get_db()
        # Check if the username is already taken
        if db.users.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html', form_data={'username': username, 'role': role})

        # Hash the password before saving for security!
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        db.users.insert_one({
            'username'  : username,
            'password'  : hashed,
            'role'      : role,
            'created_at': datetime.utcnow(),
        })
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form_data={})


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication route. Starts a session upon success."""
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login.html', form_data={'username': username})

        db, _ = get_db()
        user = db.users.find_one({'username': username})

        # Verify password using bcrypt's secure check
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'] if isinstance(user['password'], bytes) else user['password'].encode('utf-8')):
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', form_data={'username': username})

        # Success! Set up the session
        session['username'] = user['username']
        session['role']     = user['role']
        session['user_id']  = str(user['_id'])

        flash(f'Welcome back, {username}!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html', form_data={})


@app.route('/logout')
def logout():
    """Clears the session and sends the user back to the login page."""
    username = session.get('username', 'User')
    session.clear()
    flash(f'{username} has been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ── Protected Routes ──────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    """Main hub for farmers and agronomists to see their recent scans and stats."""
    db, conn_type = get_db()
    role          = session['role']
    username      = session['username']

    # Fetch last 6 scans to show on the dashboard
    recent_preds = list(db.predictions.find(
        {'username': username},
        {'image_data': 0}
    ).sort('created_at', -1).limit(6))
    recent_preds = _format_predictions(recent_preds)

    stats = _build_stats(db, username)

    # Render the appropriate dashboard template based on the user's role
    template = 'farmer_dashboard.html' if role == 'farmer' else 'agronomist_dashboard.html'
    return render_template(template,
                           predictions=recent_preds,
                           stats=stats,
                           conn_type=conn_type,
                           class_names=ml_model.get_class_names())


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handles the core feature: uploading a leaf image for disease analysis."""
    if request.method == 'POST':
        # Initial file validation
        if 'image' not in request.files:
            flash('No file was selected.', 'danger')
            return redirect(url_for('upload'))

        file = request.files['image']
        if not file or file.filename == '':
            flash('No file was selected.', 'danger')
            return redirect(url_for('upload'))

        if not _allowed_file(file.filename):
            flash('Only JPG, JPEG, and PNG images are allowed.', 'danger')
            return redirect(url_for('upload'))

        image_bytes = file.read()

        # Check if it's actually an image before sending it to the ML model
        if not ml_model.is_valid_image(image_bytes):
            flash('The file appears to be corrupted or is not a valid image.', 'danger')
            return redirect(url_for('upload'))

        # Run AI Inference
        try:
            result = ml_model.predict(image_bytes)
        except Exception as exc:
            flash(f'AI analysis failed: {exc}', 'danger')
            return redirect(url_for('upload'))

        # If the AI thinks it's not a pumpkin leaf, we reject it
        if not result['is_valid_prediction']:
            flash('Image rejected: It doesn\'t look like a pumpkin/cucurbit leaf. Please try a clearer shot.', 'warning')
            return redirect(url_for('upload'))

        # Find matching treatment advice from our database
        db, _ = get_db()
        treatment_doc = db.treatments.find_one({'disease': result['predicted_class']}, {'_id': 0})
        treatment_data = treatment_doc if treatment_doc else {}

        # Save the scan results to the history
        image_b64 = ml_model.image_to_base64(image_bytes)
        pred_doc = {
            'username'        : session['username'],
            'role'            : session['role'],
            'predicted_class' : result['predicted_class'],
            'confidence'      : result['confidence'],
            'confidence_pct'  : result['confidence_pct'],
            'all_probabilities': result['all_probabilities'],
            'all_probs_sorted': result['all_probs_sorted'],
            'treatment'       : treatment_data,
            'image_data'      : image_b64,
            'created_at'      : datetime.utcnow(),
        }
        pred_id = db.predictions.insert_one(pred_doc).inserted_id

        return redirect(url_for('result', prediction_id=str(pred_id)))

    return render_template('upload.html')


@app.route('/result/<prediction_id>')
@login_required
def result(prediction_id):
    """View detailed information about a specific scan, including treatment advice."""
    db, _ = get_db()
    try:
        oid  = ObjectId(prediction_id)
        pred = db.predictions.find_one({'_id': oid})
    except Exception:
        flash('Scan record not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Security check: users can only see their own scan results
    if not pred or pred['username'] != session['username']:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    pred['_id']  = str(pred['_id'])
    pred['date'] = (pred['created_at'].strftime('%Y-%m-%d %H:%M') if pred.get('created_at') else 'N/A')

    return render_template('result.html', prediction=pred, role=session['role'], class_names=ml_model.get_class_names())


@app.route('/history')
@login_required
def history():
    """Display all previous scans for the logged-in user."""
    db, conn_type = get_db()
    preds = list(db.predictions.find({'username': session['username']}, {'image_data': 0}).sort('created_at', -1))
    preds = _format_predictions(preds)

    return render_template('history.html', predictions=preds, conn_type=conn_type, role=session['role'])


# ── Export Routes ─────────────────────────────────────────────────────────────
@app.route('/export/json')
@login_required
def export_json():
    """Download the user's scan history in JSON format."""
    db, _ = get_db()
    preds = list(db.predictions.find({'username': session['username']}, {'image_data': 0}).sort('created_at', -1))

    for p in preds:
        p['_id'] = str(p['_id'])
        if 'created_at' in p: p['created_at'] = p['created_at'].isoformat()

    payload = json.dumps(preds, indent=2, ensure_ascii=False)
    fname   = f"cropguard_{session['username']}_history.json"
    return Response(payload, mimetype='application/json', headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@app.route('/export/csv')
@login_required
def export_csv():
    """Download the user's scan history in CSV format for spreadsheet apps."""
    db, _ = get_db()
    preds = list(db.predictions.find({'username': session['username']}, {'image_data': 0}).sort('created_at', -1))

    output  = io.StringIO()
    writer  = csv.writer(output)
    headers = ['ID', 'Date', 'Predicted Disease', 'Confidence (%)']
    for cls in ml_model.get_class_names(): headers.append(f'{cls} (%)')
    writer.writerow(headers)

    for p in preds:
        probs = p.get('all_probabilities', {})
        row   = [
            str(p['_id']),
            p['created_at'].strftime('%Y-%m-%d %H:%M') if p.get('created_at') else '',
            p.get('predicted_class', ''),
            p.get('confidence_pct', ''),
        ]
        for cls in ml_model.get_class_names(): row.append(f"{probs.get(cls, 0) * 100:.2f}")
        writer.writerow(row)

    output.seek(0)
    fname = f"cropguard_{session['username']}_history.csv"
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{fname}"'})


# ── Context processor ─────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    """Injects useful variables into every HTML template automatically."""
    return {
        'app_name'       : 'CropGuard',
        'copyright_year' : '2025-2026',
        'copyright_owner': 'U.J Tharushi Thathsarani w1953807',
        'conn_type'      : get_connection_type(),
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Initialize the ML engine before starting the web server
    ml_model.load_model()
    app.run(debug=False, host='0.0.0.0', port=5000)
