"""
app.py — CropGuard Flask Application v2.0
Copyright U.J Tharushi Thathsarani w1953807 2025-2026
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


# ── Decorators ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def _inner(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return _inner


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def _inner(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return _inner
    return decorator


# ── Helpers ───────────────────────────────────────────────────────────────────
def _allowed_file(filename: str) -> bool:
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS)


def _format_predictions(preds: list) -> list:
    """Stringify ObjectId and format dates for template rendering."""
    for p in preds:
        p['_id'] = str(p['_id'])
        p['date'] = (p['created_at'].strftime('%Y-%m-%d %H:%M')
                     if p.get('created_at') else 'N/A')
    return preds


def _build_stats(db, username: str) -> dict:
    """Return prediction statistics for a user."""
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
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', '').lower()

        # Validation
        errors = []
        if not username:
            errors.append('Username is required.')
        if not password:
            errors.append('Password is required.')
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if role not in ('farmer', 'agronomist'):
            errors.append('Please select a valid role.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html',
                                   form_data={'username': username, 'role': role})

        db, _ = get_db()
        if db.users.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html', form_data={'username': username, 'role': role})

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

        if not user:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', form_data={'username': username})

        # Ensure hashed password is in bytes format for bcrypt
        hashed_pw = user['password']
        if isinstance(hashed_pw, str):
            hashed_pw = hashed_pw.encode('utf-8')

        if not bcrypt.checkpw(password.encode('utf-8'), hashed_pw):
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', form_data={'username': username})

        session['username'] = user['username']
        session['role']     = user['role']
        session['user_id']  = str(user['_id'])

        flash(f'Welcome back, {username}!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html', form_data={})


@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    session.clear()
    flash(f'{username} has been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ── Protected Routes ──────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    db, conn_type = get_db()
    role          = session['role']
    username      = session['username']

    recent_preds = list(db.predictions.find(
        {'username': username},
        {'image_data': 0}
    ).sort('created_at', -1).limit(6))
    recent_preds = _format_predictions(recent_preds)

    stats = _build_stats(db, username)

    if role == 'farmer':
        return render_template('farmer_dashboard.html',
                               predictions=recent_preds,
                               stats=stats,
                               conn_type=conn_type)
    else:
        return render_template('agronomist_dashboard.html',
                               predictions=recent_preds,
                               stats=stats,
                               conn_type=conn_type,
                               class_names=ml_model.get_class_names())


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # ── File validation ───────────────────────────────────────────────────
        if 'image' not in request.files:
            flash('No file was selected.', 'danger')
            return redirect(url_for('upload'))

        file = request.files['image']
        if not file or file.filename == '':
            flash('No file was selected.', 'danger')
            return redirect(url_for('upload'))

        if not _allowed_file(file.filename):
            flash('Invalid file type. Please upload a JPG, JPEG, or PNG image.', 'danger')
            return redirect(url_for('upload'))

        image_bytes = file.read()

        # ── Validate actual image content ─────────────────────────────────────
        if not ml_model.is_valid_image(image_bytes):
            flash('The uploaded file could not be read as a valid image.', 'danger')
            return redirect(url_for('upload'))

        # ── Run inference ─────────────────────────────────────────────────────
        try:
            result = ml_model.predict(image_bytes)
        except Exception as exc:
            flash(f'An error occurred during analysis: {exc}', 'danger')
            return redirect(url_for('upload'))

        # ── Non-related image rejection ───────────────────────────────────────
        if not result['is_valid_prediction']:
            flash(
                f'The uploaded image does not appear to be a pumpkin/cucurbit leaf image '
                f'(maximum confidence: {result["confidence_pct"]}%). '
                f'Please upload a clear photograph of a pupkin/cucurbit leaf.',
                'warning'
            )
            return redirect(url_for('upload'))

        # ── Fetch treatment from DB ───────────────────────────────────────────
        db, _ = get_db()
        treatment_doc = db.treatments.find_one(
            {'disease': result['predicted_class']},
            {'_id': 0}
        )
        treatment_data = treatment_doc if treatment_doc else {}

        # ── Encode & save to DB ───────────────────────────────────────────────
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
    db, _ = get_db()
    try:
        oid  = ObjectId(prediction_id)
        pred = db.predictions.find_one({'_id': oid})
    except Exception:
        flash('Prediction record not found.', 'danger')
        return redirect(url_for('dashboard'))

    if not pred or pred['username'] != session['username']:
        flash('Access denied or prediction not found.', 'danger')
        return redirect(url_for('dashboard'))

    pred['_id']  = str(pred['_id'])
    pred['date'] = (pred['created_at'].strftime('%Y-%m-%d %H:%M')
                    if pred.get('created_at') else 'N/A')

    return render_template('result.html',
                           prediction=pred,
                           role=session['role'],
                           class_names=ml_model.get_class_names())


@app.route('/history')
@login_required
def history():
    db, conn_type = get_db()
    preds = list(db.predictions.find(
        {'username': session['username']},
        {'image_data': 0}
    ).sort('created_at', -1))
    preds = _format_predictions(preds)

    return render_template('history.html',
                           predictions=preds,
                           conn_type=conn_type,
                           role=session['role'])


# ── Export Routes ─────────────────────────────────────────────────────────────
@app.route('/export/json')
@login_required
def export_json():
    db, _ = get_db()
    preds = list(db.predictions.find(
        {'username': session['username']},
        {'image_data': 0}
    ).sort('created_at', -1))

    for p in preds:
        p['_id'] = str(p['_id'])
        if 'created_at' in p:
            p['created_at'] = p['created_at'].isoformat()

    payload = json.dumps(preds, indent=2, ensure_ascii=False)
    fname   = f"cropguard_{session['username']}_history.json"
    return Response(
        payload,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'}
    )


@app.route('/export/csv')
@login_required
def export_csv():
    db, _ = get_db()
    preds = list(db.predictions.find(
        {'username': session['username']},
        {'image_data': 0}
    ).sort('created_at', -1))

    output  = io.StringIO()
    writer  = csv.writer(output)
    headers = ['ID', 'Date', 'Predicted Disease', 'Confidence (%)']
    for cls in ml_model.get_class_names():
        headers.append(f'{cls} (%)')
    writer.writerow(headers)

    for p in preds:
        probs = p.get('all_probabilities', {})
        row   = [
            str(p['_id']),
            p['created_at'].strftime('%Y-%m-%d %H:%M') if p.get('created_at') else '',
            p.get('predicted_class', ''),
            p.get('confidence_pct', ''),
        ]
        for cls in ml_model.get_class_names():
            row.append(f"{probs.get(cls, 0) * 100:.2f}")
        writer.writerow(row)

    output.seek(0)
    fname = f"cropguard_{session['username']}_history.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'}
    )


# ── Context processor (inject globals into every template) ────────────────────
@app.context_processor
def inject_globals():
    return {
        'app_name'       : 'CropGuard',
        'copyright_year' : '2025-2026',
        'copyright_owner': 'U.J Tharushi Thathsarani w1953807',
        'conn_type'      : get_connection_type(),
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Loading CropGuard ML model...")
    ml_model.load_model()
    print("Model ready. Starting Flask server...")
    app.run(debug=False, host='0.0.0.0', port=5000)
