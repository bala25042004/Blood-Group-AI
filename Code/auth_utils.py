"""
Authentication utilities for OTP and Google OAuth integration
Handles SMS OTP verification and third-party OAuth
"""

import random
import string
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for

# ============================================================================
# OTP MANAGEMENT (Requires Twilio account for production)
# ============================================================================

class OTPManager:
    """Manages OTP generation and verification"""
    
    @staticmethod
    def generate_otp(length=6):
        """Generate a random OTP"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def save_otp(phone_number, otp, db_path='database.db'):
        """Save OTP to database with 10-minute expiry"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                expiry_time = datetime.now() + timedelta(minutes=10)
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS otp_verification (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phone_number TEXT NOT NULL,
                        otp TEXT NOT NULL,
                        expiry_time TIMESTAMP NOT NULL,
                        verified INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    INSERT INTO otp_verification (phone_number, otp, expiry_time)
                    VALUES (?, ?, ?)
                ''', (phone_number, otp, expiry_time))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving OTP: {e}")
            return False
    
    @staticmethod
    def verify_otp(phone_number, otp, db_path='database.db'):
        """Verify if OTP is correct and not expired"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now()
                
                cursor.execute('''
                    SELECT id, otp, expiry_time FROM otp_verification
                    WHERE phone_number = ? AND verified = 0
                    ORDER BY created_at DESC LIMIT 1
                ''', (phone_number,))
                
                result = cursor.fetchone()
                
                if not result:
                    return False, "No OTP found for this number"
                
                otp_id, stored_otp, expiry_time = result
                expiry = datetime.fromisoformat(expiry_time)
                
                if current_time > expiry:
                    return False, "OTP has expired. Please request a new one"
                
                if stored_otp != otp:
                    return False, "OTP is incorrect"
                
                # Mark as verified
                cursor.execute('''
                    UPDATE otp_verification SET verified = 1 WHERE id = ?
                ''', (otp_id,))
                conn.commit()
                
                return True, "OTP verified successfully"
        except Exception as e:
            return False, f"Verification error: {str(e)}"
    
    @staticmethod
    def send_otp_twilio(phone_number, otp):
        """
        Send OTP via Twilio SMS
        
        SETUP REQUIRED:
        1. Install Twilio: pip install twilio
        2. Get Twilio credentials from https://www.twilio.com/console
        3. Set environment variables:
           - TWILIO_ACCOUNT_SID
           - TWILIO_AUTH_TOKEN
           - TWILIO_PHONE_NUMBER
        """
        try:
            from twilio.rest import Client
            import os
            
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            from_number = os.getenv('TWILIO_PHONE_NUMBER')
            
            if not all([account_sid, auth_token, from_number]):
                print("WARNING: Twilio credentials not configured")
                print("For production SMS, set environment variables:")
                print("  - TWILIO_ACCOUNT_SID")
                print("  - TWILIO_AUTH_TOKEN")
                print("  - TWILIO_PHONE_NUMBER")
                return False
            
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=f"Your Blood Eye verification OTP is: {otp}\nValid for 10 minutes.",
                from_=from_number,
                to=phone_number
            )
            return True
        except ImportError:
            print("WARNING: Twilio not installed. Install with: pip install twilio")
            return False
        except Exception as e:
            print(f"Error sending OTP: {e}")
            return False


# ============================================================================
# GOOGLE OAUTH SETUP
# ============================================================================

def setup_google_oauth(app):
    """
    Configure Google OAuth for Flask application
    
    SETUP REQUIRED:
    1. Install dependencies: pip install flask-dance google-auth google-auth-oauthlib
    2. Create OAuth credentials:
       - Go to https://console.cloud.google.com/
       - Create a new project: "Blood Eye Project"
       - Enable Google+ API
       - Create OAuth 2.0 Credentials (Web application)
       - Set Authorized redirect URIs:
         * http://localhost:5000/login/google/authorized
         * https://yourdomain.com/login/google/authorized
    3. Save credentials as .env file:
       GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
       GOOGLE_CLIENT_SECRET=your_client_secret
    """
    try:
        from flask_dance.contrib.google import make_google_blueprint, google
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # For local development over HTTP
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        
        google_client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
        google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
        
        if not google_client_id or not google_client_secret:
            print("WARNING: Google OAuth credentials not configured")
            print("Set environment variables:")
            print("  - GOOGLE_CLIENT_ID")
            print("  - GOOGLE_CLIENT_SECRET")
            return None
        
        google_bp = make_google_blueprint(
            client_id=google_client_id,
            client_secret=google_client_secret,
            scope=['profile', 'email'],
            redirect_to='google_authorized'
        )
        
        app.register_blueprint(google_bp, url_prefix='/login')
        return google_bp
        
    except ImportError as e:
        print(f"WARNING: Flask-Dance not installed: {e}")
        print("Install with: pip install flask-dance python-dotenv")
        return None
    except Exception as e:
        print(f"Error setting up Google OAuth: {e}")
        return None


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user(db_path='database.db'):
    """Get current logged-in user from session"""
    if 'user_id' not in session:
        return None
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username FROM users WHERE id = ?', (session['user_id'],))
            result = cursor.fetchone()
            return result
    except:
        return None
