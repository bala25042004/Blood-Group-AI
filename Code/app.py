import os
import sqlite3
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
from werkzeug.utils import secure_filename
from auth_utils import OTPManager, login_required, get_current_user, setup_google_oauth
from tensorflow.keras.models import load_model
import joblib
import uuid
import io
import random
import string
from datetime import datetime
from dotenv import load_dotenv

# PDF and QR imports
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch
import qrcode

# Import updated feature extraction functions
from feature_Code_fundus import extract_fundus_features
from feature_Code_scelera import extract_sclera_features

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['STATIC_FOLDER'] = 'static'
app.config['DATABASE'] = 'database.db'

# Setup Google OAuth
setup_google_oauth(app)

# Updated feature list: 5 from fundus + 5 from sclera
ALL_FEATURES = [
    'fundus_cnn_pca1', 'fundus_AVR', 'fundus_vessel_redness',
    'fundus_tortuosity', 'fundus_vessel_density',
    'sclera_cnn_pca1', 'sclera_AVR', 'sclera_mean_hue',
    'sclera_redness', 'sclera_perivascular_contrast'
]

db_setup_done = False

def init_db():
    with sqlite3.connect(app.config['DATABASE']) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Check if columns exist (for migration)
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'email' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if 'phone' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
        conn.commit()

@app.before_request
def setup_app():
    global db_setup_done
    if not db_setup_done:
        init_db()
        if not all(os.path.exists(f) for f in ['trained_model.h5', 'scaler.pkl', 'encoder.pkl']):
            print("Model files are missing. Running automatic training...")
            try:
                train_and_evaluate_model('eye_dataset2.csv')
                print("Automatic training complete. Model files are now available.")
            except FileNotFoundError:
                print("Error: 'eye_dataset2.csv' not found.")
            except Exception as e:
                print(f"An error occurred during automatic training: {e}")
        db_setup_done = True



@app.route('/')
def home():
    # Redirect to login if not authenticated
    if 'user_id' not in session and 'username' not in session:
        return render_template('index.html')
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        email = request.form.get('email', '')
        
        # Validation
        if not username or not password:
            return render_template('register_enhanced.html', error='Username and password required')
        
        if password != confirm_password:
            return render_template('register_enhanced.html', error='Passwords do not match')
        
        if len(password) < 8:
            return render_template('register_enhanced.html', error='Password must be at least 8 characters')
        
        try:
            init_db()  # Ensure table is ready
            with sqlite3.connect(app.config['DATABASE']) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", 
                              (username, password, email))
                conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register_enhanced.html', error='Username already exists. Choose another.')
    return render_template('register_enhanced.html')


@app.route('/send-otp', methods=['POST'])
def send_otp():
    """Send OTP to user's phone number"""
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        
        if not phone or len(phone) < 10:
            return jsonify({'success': False, 'message': 'Invalid phone number'})
        
        # Generate and save OTP
        otp = OTPManager.generate_otp()
        OTPManager.save_otp(phone, otp, app.config['DATABASE'])
        
        # Try to send via Twilio (optional)
        OTPManager.send_otp_twilio(phone, otp)
        
        # For development: log OTP
        print(f"[DEV] OTP for {phone}: {otp}")
        
        # Store phone in session for verification
        session['pending_phone'] = phone
        
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP sent to user"""
    try:
        data = request.get_json()
        otp = data.get('otp', '')
        phone = session.get('pending_phone', '')
        
        if not phone:
            return jsonify({'success': False, 'message': 'No phone number in session. Please try again.'})
        
        # Verify OTP
        success, message = OTPManager.verify_otp(phone, otp, app.config['DATABASE'])
        
        if success:
            session['otp_verified'] = True
            session['verified_phone'] = phone
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/register-mobile', methods=['POST'])
def register_mobile():
    """Complete registration with mobile OTP verification"""
    try:
        # Check if OTP was verified
        if not session.get('otp_verified'):
            return jsonify({'success': False, 'message': 'Please verify OTP first'})
        
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')
        phone = session.get('verified_phone', '')
        
        if not all([username, password, phone]):
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'})
        
        # Create user account
        init_db()
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, phone) VALUES (?, ?, ?)",
                          (username, password, phone))
            conn.commit()
        
        # Clean up session
        session.pop('otp_verified', None)
        session.pop('verified_phone', None)
        session.pop('pending_phone', None)
        
        return jsonify({'success': True, 'message': 'Account created successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", 
                          (username, password))
            user = cursor.fetchone()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            if remember:
                session.permanent = True
            return redirect(url_for('home'))
        else:
            return render_template('login_enhanced.html', error='Invalid username or password')
    
    return render_template('login_enhanced.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('otp_verified', None)
    session.pop('verified_phone', None)
    session.pop('pending_phone', None)
    return redirect(url_for('home'))


# ============================================================================
# GOOGLE OAUTH HANDLER (Optional - requires configuration)
# ============================================================================
# To enable Google OAuth:
# 1. Install: pip install flask-dance python-dotenv
# 2. Create .env file with GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
# 3. Uncomment the setup_google_oauth call in the app initialization

@app.route('/google_authorized')
def google_authorized():
    """Handle landing after Google OAuth success"""
    try:
        # This requires flask-dance to be installed and configured
        # The Google OAuth token is automatically handled by flask-dance
        
        from flask_dance.contrib.google import google
        
        if not google.authorized:
            return redirect(url_for('login'))
        
        # Get user info from Google
        resp = google.get('/oauth2/v2/userinfo')
        user_info = resp.json()
        email = user_info.get('email', '')
        name = user_info.get('name', email.split('@')[0])
        
        # Check if user exists, create if not
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            
            if not user:
                # Create new user from Google info
                username = name.replace(' ', '_').lower()[:20]
                cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
                if cursor.fetchone()[0] > 0:
                    username = f"{username}_{str(uuid.uuid4())[:8]}"
                
                cursor.execute('''
                    INSERT INTO users (username, email, password)
                    VALUES (?, ?, ?)
                ''', (username, email, str(uuid.uuid4())))
                conn.commit()
                cursor.execute("SELECT id, username FROM users WHERE email = ?", (email,))
                user = cursor.fetchone()
        
        # Login user
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['google_oauth'] = True
        
        return redirect(url_for('home'))
    except ImportError:
        return render_template('login_enhanced.html', error='Google OAuth not configured. Please use username/password login.')
    except Exception as e:
        print(f"Google OAuth error: {e}")
        return render_template('login_enhanced.html', error=f'Google login failed: {str(e)}')

@app.route('/working')
def working():
    return render_template('working.html')

@app.route('/ai_scanner', endpoint='ai_scanner')
@app.route('/scanner')
@login_required
def ai_scanner():
    """UI entry for the dual fundus/sclera scanner."""
    return render_template('ai_scanner.html')

@app.route('/fundus_upload', methods=['GET', 'POST'])
@login_required
def fundus_upload():
    if request.method == 'POST':
        if 'image' not in request.files:
            return jsonify({'error': 'No file part'})
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        if file:
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            try:
                features, processed_image_filename = extract_fundus_features(filepath)
                features = {key: float(value) for key, value in features.items()}
                session['fundus_features'] = features
                
                processed_image_path = url_for('static', filename=f"uploads/{processed_image_filename}")
                
                return jsonify({
                    'success': True,
                    'features': features,
                    'processed_image_path': processed_image_path
                })
            except Exception as e:
                return jsonify({'error': str(e)})
    return render_template('fundus_upload.html')

@app.route('/save_patient', methods=['POST'])
@login_required
def save_patient():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    age = data.get('age', '').strip()
    gender = data.get('gender', '').strip()

    if not name or not age or not gender:
        return jsonify({'success': False, 'message': 'All fields required'})

    session['patient'] = {'name': name, 'age': age, 'gender': gender}
    return jsonify({'success': True})


@app.route('/patient_info', methods=['GET'])
@login_required
def patient_info():
    patient = session.get('patient', {})
    if not patient:
        return jsonify({'success': False, 'message': 'No patient details saved yet.'})
    return jsonify({'success': True, 'patient': patient})

@app.route('/sclera_upload', methods=['GET', 'POST'])
@login_required
def sclera_upload():
    if request.method == 'POST':
        if 'image' not in request.files:
            return jsonify({'error': 'No file part'})
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        if file:
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)

            try:
                features, processed_image_filename = extract_sclera_features(filepath)
                features = {key: float(value) for key, value in features.items()}
                session['sclera_features'] = features
                
                processed_image_path = url_for('static', filename=f"uploads/{processed_image_filename}")
                
                return jsonify({
                    'success': True,
                    'features': features,
                    'processed_image_path': processed_image_path
                })
            except Exception as e:
                return jsonify({'error': str(e)})
    return render_template('sclera_upload.html')

@app.route('/predict_ajax', methods=['GET'])
@login_required
def predict_ajax():
    fundus_features = session.get('fundus_features', None)
    sclera_features = session.get('sclera_features', None)

    if not fundus_features or not sclera_features:
        return jsonify({'success': False, 'message': 'Please upload and extract both images first.'})

    all_features_dict = {**fundus_features, **sclera_features}
    for f in ALL_FEATURES:
        if f not in all_features_dict:
            return jsonify({'success': False, 'message': f'Missing feature: {f}'})

    input_data = [all_features_dict[f] for f in ALL_FEATURES]
    input_data = np.array(input_data).reshape(1, -1)

    try:
        if not os.path.exists('trained_model.h5') or not os.path.exists('scaler.pkl') or not os.path.exists('encoder.pkl'):
            return jsonify({'success': False, 'message': 'Model files missing. Please train the model.'})

        model = load_model('trained_model.h5', compile=False)
        scaler = joblib.load('scaler.pkl')
        encoder = joblib.load('encoder.pkl')

        scaled_data = scaler.transform(input_data)
        prediction = model.predict(scaled_data, verbose=0)
        predicted_label = np.argmax(prediction, axis=1)
        predicted_blood_group = encoder.inverse_transform(predicted_label)[0]
        session['predicted_blood_group'] = str(predicted_blood_group)
        return jsonify({'success': True, 'predicted_blood_group': str(predicted_blood_group)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error in prediction: {e}'})

def get_feature_status(key, value):
    kn = key.upper()
    status = 'Normal'
    if 'FUNDUS' in kn:
        if 'AVR' in kn:
            status = 'Low' if value < 0.60 else 'High / Risk' if value > 0.75 else 'Normal'
        elif 'TORTUOSITY' in kn:
            status = 'Low' if value < 1.0 else 'High / Risk' if value > 1.15 else 'Normal'
        elif 'VESSEL_DENSITY' in kn:
            status = 'Low' if value < 0.30 else 'High / Risk' if value > 0.60 else 'Normal'
        elif 'VESSEL_REDNESS' in kn or 'REDNESS' in kn:
            status = 'Low' if value < 40 else 'High / Risk' if value > 100 else 'Normal'
        elif 'CNN_PCA1' in kn:
            status = 'Low' if value < -1.0 else 'High / Risk' if value > 1.0 else 'Normal'
    elif 'SCLERA' in kn:
        if 'AVR' in kn:
            status = 'Low' if value < 0.80 else 'High / Risk' if value > 1.20 else 'Normal'
        elif 'REDNESS' in kn:
            status = 'Low' if value < 50 else 'High / Risk' if value > 120 else 'Normal'
        elif 'MEAN_HUE' in kn:
            status = 'Low' if value < 5 else 'High / Risk' if value > 20 else 'Normal'
        elif 'PERIVASCULAR_CONTRAST' in kn:
            status = 'Low' if value < -2 else 'High / Risk' if value > 5 else 'Normal'
        elif 'CNN_PCA1' in kn:
            status = 'Low' if value < -1.0 else 'High / Risk' if value > 1.0 else 'Normal'
    return status

def get_feature_range(key):
    kn = key.upper()
    if 'FUNDUS' in kn:
        if 'AVR' in kn: return '0.60 – 0.75'
        elif 'TORTUOSITY' in kn: return '1.0 – 1.15'
        elif 'VESSEL_DENSITY' in kn: return '0.30 – 0.60'
        elif 'VESSEL_REDNESS' in kn or 'REDNESS' in kn: return '40 – 100'
        elif 'CNN_PCA1' in kn: return '-1.0 – 1.0'
    elif 'SCLERA' in kn:
        if 'AVR' in kn: return '0.80 – 1.20'
        elif 'REDNESS' in kn: return '50 – 120'
        elif 'MEAN_HUE' in kn: return '5 – 20'
        elif 'PERIVASCULAR_CONTRAST' in kn: return '-2 – 5'
        elif 'CNN_PCA1' in kn: return '-1.0 – 1.0'
    return ''

@app.route('/results')
@login_required
def results():
    fundus_features = session.get('fundus_features', None)
    sclera_features = session.get('sclera_features', None)

    if not fundus_features or not sclera_features:
        return render_template('results.html', error='Please upload both fundus and sclera images first.')

    # Combine selected features
    all_features_dict = {**fundus_features, **sclera_features}

    # Check for missing features
    for f in ALL_FEATURES:
        if f not in all_features_dict:
            return render_template('results.html', error=f"Missing feature: {f}")

    input_data = [all_features_dict[f] for f in ALL_FEATURES]
    input_data = np.array(input_data).reshape(1, -1)

    try:
        if not os.path.exists('trained_model.h5') or not os.path.exists('scaler.pkl') or not os.path.exists('encoder.pkl'):
            return render_template('results.html', error="Model files missing. Please train the model.")

        model = load_model('trained_model.h5', compile=False)
        scaler = joblib.load('scaler.pkl')
        encoder = joblib.load('encoder.pkl')

        scaled_data = scaler.transform(input_data)
        prediction = model.predict(scaled_data, verbose=0)
        predicted_label = np.argmax(prediction, axis=1)
        predicted_blood_group = encoder.inverse_transform(predicted_label)[0]
    except Exception as e:
        predicted_blood_group = f"Error in prediction: {e}"

    fundus_statuses = {k: get_feature_status(k, v) for k, v in fundus_features.items()}
    sclera_statuses = {k: get_feature_status(k, v) for k, v in sclera_features.items()}
    fundus_ranges = {k: get_feature_range(k) for k in fundus_features.keys()}
    sclera_ranges = {k: get_feature_range(k) for k in sclera_features.keys()}
    has_abnormal = any(s != 'Normal' for s in fundus_statuses.values()) or any(s != 'Normal' for s in sclera_statuses.values())

    return render_template('results.html', 
                           fundus_features=fundus_features, 
                           sclera_features=sclera_features, 
                           fundus_statuses=fundus_statuses,
                           sclera_statuses=sclera_statuses,
                           fundus_ranges=fundus_ranges,
                           sclera_ranges=sclera_ranges,
                           has_abnormal=has_abnormal,
                           predicted_blood_group=predicted_blood_group)

@app.route('/download_report')
@login_required
def download_report():
    """Generate and download a Blood Eye Project AI Diagnostic PDF report"""
    # Get current user and analysis data from session
    patient = session.get('patient', {})
    predicted_blood_group = session.get('predicted_blood_group', 'Unknown')
    fundus_features = session.get('fundus_features', {})
    sclera_features = session.get('sclera_features', {})
    
    # Use default values for patient info
    name = patient.get('name', 'N/A').upper()
    age = patient.get('age', 'N/A')
    gender = patient.get('gender', 'N/A').capitalize()
    
    # Parse Blood Group into ABO and Rh Factor
    abo_group = "N/A"
    rh_factor = "N/A"
    if predicted_blood_group != 'Unknown' and predicted_blood_group:
        # Regex or simple string split for + and -
        if '+' in predicted_blood_group:
            abo_group = predicted_blood_group.split('+')[0].strip()
            rh_factor = "Positive"
        elif '-' in predicted_blood_group:
            abo_group = predicted_blood_group.split('-')[0].strip()
            rh_factor = "Negative"
        else:
            abo_group = predicted_blood_group
            rh_factor = "N/A"
    
    # Generate unique IDs
    report_id = 'REP-' + ''.join(random.choices(string.digits, k=8))
    patient_id = 'P-' + ''.join(random.choices(string.digits, k=6))
    timestamp = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    
    # Create QR data covering patient info
    qr_content = f"ID: {patient_id}\nName: {name}\nAge/Sex: {age}/{gender[0]}\nGroup: {predicted_blood_group}"
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(qr_content)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # PDF Setup
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Custom Styles for Modern Report
    title_style = ParagraphStyle(
        'ReportHeader', parent=styles['Heading1'], fontSize=20, alignment=1, spaceAfter=20, textColor=colors.black, fontName='Helvetica-Bold'
    )
    section_header = ParagraphStyle(
        'SectionHeader', parent=styles['Heading2'], fontSize=11, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=8, textColor=colors.darkblue
    )
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    
    story = []
    
    # 1. Main Title
    story.append(Paragraph("<b>BLOOD EYE PROJECT - DIAGNOSTIC REPORT</b>", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # 2. Patient Details Table with QR Code
    # Table layout: [Left Info Col, Right Info Col, QR Col]
    info_left = [
        [Paragraph("<b>Name:</b>", normal_style), Paragraph(name, normal_style)],
        [Paragraph("<b>Age:</b>", normal_style), Paragraph(age, normal_style)],
        [Paragraph("<b>Sex:</b>", normal_style), Paragraph(gender, normal_style)]
    ]
    info_right = [
        [Paragraph("<b>Patient ID:</b>", normal_style), Paragraph(patient_id, normal_style)],
        [Paragraph("<b>Report ID:</b>", normal_style), Paragraph(report_id, normal_style)],
        [Paragraph("<b>Date:</b>", normal_style), Paragraph(timestamp, normal_style)]
    ]
    
    # Inner tables for layout
    t_left = Table(info_left, colWidths=[0.8*inch, 2*inch])
    t_left.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
    
    t_right = Table(info_right, colWidths=[1.1*inch, 1.8*inch])
    t_right.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    
    qr_box = Image(qr_buffer, width=0.9*inch, height=0.9*inch)
    
    # Combine into a master patient header table
    header_data = [[t_left, t_right, qr_box]]
    header_table = Table(header_data, colWidths=[2.8*inch, 2.9*inch, 1.3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.lightgrey),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))
    
    # 3. Investigation / Test Details Table
    story.append(Paragraph("<b>INVESTIGATION / TEST DETAILS</b>", section_header))
    
    test_data = [
        ['Investigation', 'Result'],
        ['ABO Grouping', abo_group],
        ['Rh Factor', rh_factor],
        ['Analysis Method', 'AI-Retinal Image Scanning']
    ]
    
    test_table = Table(test_data, colWidths=[3.5*inch, 3.5*inch])
    test_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F4F8")), # Light blue highlight
        ('TEXTCOLOR', (0,0), (-1,0), colors.darkblue),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'), # Left align investigation names- but header should be center
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
    ]))
    story.append(test_table)
    story.append(Spacer(1, 0.3*inch))

    # 4. Analysis Metrics / Extracted FeaturesSection
    story.append(Paragraph("<b>ANALYSIS METRICS / EXTRACTED FEATURES</b>", section_header))
    
    metrics_data = [['Metric / Feature Name', 'Calculated Value', 'Reference Range']]
    # Combine fundus and sclera features
    all_features = {**fundus_features, **sclera_features}
    has_abnormal = False
    for key, val in all_features.items():
        status = get_feature_status(key, val)
        rng = get_feature_range(key)
        if status != 'Normal':
            has_abnormal = True
        
        status_text = ""
        if status == 'Normal':
            status_text = " (Normal)"
        elif status == 'Low':
            status_text = " (Low)"
        elif status == 'High / Risk':
            status_text = " (High / Risk)"
            
        metrics_data.append([
            key.replace('_', ' ').upper(), 
            f"{val:.4f}{status_text}",
            rng
        ])
    
    if len(metrics_data) > 1:
        metrics_table = Table(metrics_data, colWidths=[3.2*inch, 2*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F8F9FA")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,0), (2,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor("#fdfdfd")]),
        ]))
        story.append(metrics_table)
        
        # Add Summary
        story.append(Spacer(1, 0.15*inch))
        if has_abnormal:
            story.append(Paragraph("<font color='red'><b>⚠️ Some values are outside normal range. Please consult a doctor.</b></font>", normal_style))
        else:
            story.append(Paragraph("<font color='green'><b>✅ All values are within normal range.</b></font>", normal_style))
    else:
        story.append(Paragraph("No metrics data available for this analysis.", normal_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # 5. Notes / Analysis Section
    story.append(Paragraph("<b>NOTES / ANALYSIS</b>", section_header))
    notes = [
        f"&bull; Analysis performed via non-invasive AI-Retinal Scanning (Report Verification ID: {report_id}).",
        "&bull; ABO and Rh Grouping are based on visual analysis of blood vessels and pigmentation."
    ]
    for note in notes:
        story.append(Paragraph(note, normal_style))
        story.append(Spacer(1, 0.08*inch))
    
    story.append(Spacer(1, 0.3*inch))
    
    # 6. Footer Line
    story.append(Paragraph("<hr/>", normal_style))
    footer_text = f"This is a computer-generated laboratory report produced by the Blood Eye Project AI System. No signature is required. | Generated at: {timestamp}"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=normal_style, fontSize=7, alignment=1, textColor=colors.grey)))
    
    # Build PDF
    doc.build(story)
    
    # Send generated PDF
    buffer.seek(0)
    pdf_content = buffer.getvalue()
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Diagnostic_Blood_Group_Report_{report_id}.pdf'
    return response

def train_and_evaluate_model(dataset_path):
    # Lazy imports — only needed for training, not normal app operation
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import confusion_matrix
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.utils import to_categorical
    from tensorflow.keras.callbacks import EarlyStopping
    import matplotlib.pyplot as plt
    import seaborn as sns

    df = pd.read_csv(dataset_path)
    features_to_use = ['cnn_pca1', 'AVR', 'vessel_redness', 'sclera_mean_hue', 'AV_sat_diff', 'tortuosity', 'sclera_redness', 'vessel_density', 'perivascular_contrast', 'pulse_std']
    target = 'blood_group'
    df_clean = df.dropna(subset=features_to_use + [target])
    X = df_clean[features_to_use]
    y = df_clean[target]

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    y_categorical = to_categorical(y_encoded)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y_categorical, test_size=0.2, random_state=42, stratify=y_encoded)
    y_test_labels = np.argmax(y_test, axis=1)

    model = Sequential([
        Dense(128, activation='relu', input_shape=(X_train.shape[1],)),
        Dropout(0.3),
        Dense(64, activation='relu'),
        Dropout(0.3),
        Dense(32, activation='relu'),
        Dropout(0.2),
        Dense(y_categorical.shape[1], activation='softmax')
    ])

    model.compile(optimizer=Adam(learning_rate=0.0005),
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    early_stopping = EarlyStopping(monitor='val_accuracy', patience=15, restore_best_weights=True)

    history = model.fit(X_train, y_train,
                        epochs=150,
                        batch_size=16,
                        validation_split=0.2,
                        callbacks=[early_stopping],
                        verbose=1)

    model.save('trained_model1.h5')
    joblib.dump(scaler, 'scaler1.pkl')
    joblib.dump(le, 'encoder1.pkl')

    # Accuracy & Loss plots
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    ax1.plot(history.history['accuracy'])
    ax1.plot(history.history['val_accuracy'])
    ax1.set_title('Model Accuracy')
    ax1.set_ylabel('Accuracy')
    ax1.set_xlabel('Epoch')
    ax1.legend(['Train', 'Validation'], loc='upper left')
    ax2.plot(history.history['loss'])
    ax2.plot(history.history['val_loss'])
    ax2.set_title('Model Loss')
    ax2.set_ylabel('Loss')
    ax2.set_xlabel('Epoch')
    ax2.legend(['Train', 'Validation'], loc='upper left')
    plt.savefig(os.path.join(app.config['STATIC_FOLDER'], 'accuracy_loss_graphs.png'))
    plt.close(fig)

    # Confusion Matrix
    y_pred_probs = model.predict(X_test, verbose=0)
    y_pred_labels = np.argmax(y_pred_probs, axis=1)
    cm = confusion_matrix(y_test_labels, y_pred_labels)
    class_names = le.classes_
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=class_names, yticklabels=class_names)
    plt.title('Confusion Matrix')
    plt.ylabel('Actual Label')
    plt.xlabel('Predicted Label')
    plt.savefig(os.path.join(app.config['STATIC_FOLDER'], 'confusion_matrix.png'))
    plt.close()

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
    app.run(debug=True, use_reloader=True)
