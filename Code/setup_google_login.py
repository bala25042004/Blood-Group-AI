#!/usr/bin/env python3
"""
Google OAuth Automatic Setup Script
====================================
This script automatically sets up Google Account Login for the Blood Eye Project.
It checks existing configuration and guides you through any missing steps.

Usage:
    python setup_google_login.py
"""

import os
import sys
import subprocess
import webbrowser
import time

# Simple text-based output
def print_step(step_num, total_steps, message):
    """Print a step header"""
    print(f"\n=== Step {step_num}/{total_steps}: {message} ===")

def print_success(message):
    """Print success message"""
    print(f"[OK] {message}")

def print_warning(message):
    """Print warning message"""
    print(f"[WARN] {message}")

def print_error(message):
    """Print error message"""
    print(f"[ERROR] {message}")

def print_info(message):
    """Print info message"""
    print(f"[INFO] {message}")

def check_env_file():
    """Check if .env file exists and has Google OAuth credentials"""
    print_step(1, 5, "Checking Environment Configuration")
    
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    env_example_path = os.path.join(os.path.dirname(__file__), '.env.example')
    
    # Check if .env exists
    if not os.path.exists(env_path):
        print_warning(".env file not found. Creating from template...")
        if os.path.exists(env_example_path):
            with open(env_example_path, 'r') as src:
                with open(env_path, 'w') as dst:
                    dst.write(src.read())
            print_success("Created .env file from template")
        else:
            with open(env_path, 'w') as f:
                f.write("""# Flask Secret Key
FLASK_SECRET_KEY=change_this_to_a_secure_random_key

# Google OAuth Credentials
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
""")
            print_success("Created new .env file")
    
    # Read current .env
    with open(env_path, 'r') as f:
        env_content = f.read()
    
    # Check for Google OAuth credentials
    has_client_id = 'GOOGLE_CLIENT_ID=' in env_content and 'apps.googleusercontent.com' in env_content
    has_client_secret = 'GOOGLE_CLIENT_SECRET=' in env_content and 'GOCSPX-' in env_content
    
    if has_client_id and has_client_secret:
        print_success("Google OAuth credentials found in .env!")
        
        # Extract values for display
        for line in env_content.split('\n'):
            if line.startswith('GOOGLE_CLIENT_ID=') and not line.startswith('#'):
                client_id = line.split('=', 1)[1].strip()
                print_info(f"Client ID: {client_id[:50]}...")
            if line.startswith('GOOGLE_CLIENT_SECRET=') and not line.startswith('#'):
                client_secret = line.split('=', 1)[1].strip()
                print_info(f"Client Secret: {client_secret[:20]}...")
        
        return True, env_path
    else:
        print_warning("Google OAuth credentials not configured")
        return False, env_path

def get_google_credentials(env_path):
    """Guide user through getting Google OAuth credentials"""
    print_step(2, 5, "Getting Google OAuth Credentials")
    
    print("""
To enable Google Login, you need OAuth 2.0 credentials from Google Cloud Console:

1. Go to: https://console.cloud.google.com/
2. Create a new project or select existing
3. Search for "Google+ API" or "People API" and enable it
4. Go to APIs & Services > Credentials
5. Click CREATE CREDENTIALS > OAuth client ID
6. Choose Web application
7. Set application name: Blood Eye Project
8. Add authorized redirect URIs:
   - http://localhost:5000/login/google/authorized
   - http://127.0.0.1:5000/login/google/authorized
9. Click CREATE
10. Copy the Client ID and Client Secret

""")
    
    # Ask if user wants to open Google Console
    response = input("Would you like to open Google Cloud Console now? (y/n): ").strip().lower()
    if response == 'y':
        webbrowser.open('https://console.cloud.google.com/')
        print_info("Please complete the steps above and return here")
        input("\nPress Enter when you have your credentials...")
    
    # Get credentials from user
    print("\nEnter your Google OAuth credentials:")
    client_id = input("Client ID (ends with .apps.googleusercontent.com): ").strip()
    client_secret = input("Client Secret (starts with GOCSPX-): ").strip()
    
    if not client_id or not client_secret:
        print_error("Credentials cannot be empty!")
        return False
    
    # Validate format
    if not client_id.endswith('.apps.googleusercontent.com'):
        print_warning("Client ID doesn't look correct (should end with .apps.googleusercontent.com)")
    
    # Update .env file
    with open(env_path, 'r') as f:
        env_content = f.read()
    
    lines = env_content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('GOOGLE_CLIENT_ID=') and not line.startswith('#'):
            new_lines.append(f'GOOGLE_CLIENT_ID={client_id}')
        elif line.startswith('GOOGLE_CLIENT_SECRET=') and not line.startswith('#'):
            new_lines.append(f'GOOGLE_CLIENT_SECRET={client_secret}')
        else:
            new_lines.append(line)
    
    with open(env_path, 'w') as f:
        f.write('\n'.join(new_lines))
    
    print_success(f"Credentials saved to .env")
    return True

def install_dependencies():
    """Install required dependencies"""
    print_step(3, 5, "Installing Dependencies")
    
    required_packages = ['flask-dance', 'google-auth', 'google-auth-oauthlib', 'python-dotenv']
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"{package} is already installed")
        except ImportError:
            print_info(f"Installing {package}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package, '-q'])
                print_success(f"Installed {package}")
            except Exception as e:
                print_error(f"Failed to install {package}: {e}")
                return False
    
    return True

def verify_google_setup():
    """Verify Google OAuth is properly configured"""
    print_step(4, 5, "Verifying Google OAuth Setup")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    
    if not client_id or not client_secret:
        print_error("Google OAuth credentials not found in environment")
        return False
    
    if not client_id.endswith('.apps.googleusercontent.com'):
        print_error("Client ID format is incorrect")
        return False
    
    print_success("Google OAuth credentials are properly configured!")
    
    # Check if Flask-Dance can be imported
    try:
        from flask_dance.contrib.google import make_google_blueprint
        print_success("Flask-Dance Google blueprint available")
    except ImportError as e:
        print_error(f"Flask-Dance not properly configured: {e}")
        return False
    
    return True

def test_login():
    """Test the login setup"""
    print_step(5, 5, "Testing Login Setup")
    
    print("""
Google OAuth Setup Complete!

To test the login:
1. Start the Flask application: python app.py
2. Open your browser to: http://localhost:5000
3. Click on Login
4. You should see a "Google" button below the login form
5. Click the Google button to sign in with your Google account

First-time setup notes:
- Google will show a warning about "Google hasn't verified this app"
- Click Advanced > Go to [Your App] (unsafe)
- This is normal for development apps

For production deployment:
- Add your production domain to authorized redirect URIs
- Complete Google Cloud verification process
""")
    
    # Ask to start the app
    response = input("\nWould you like to start the application now? (y/n): ").strip().lower()
    if response == 'y':
        print_info("Starting Flask application...")
        subprocess.Popen([sys.executable, 'app.py'])
        time.sleep(3)
        webbrowser.open('http://localhost:5000')
    
    return True

def main():
    """Main setup function"""
    print("""
=======================================================================
       Google OAuth Login Setup - Blood Eye Project
=======================================================================
    """)
    
    # Change to Code directory
    os.chdir(os.path.dirname(__file__))
    
    # Step 1: Check environment
    has_credentials, env_path = check_env_file()
    
    # Step 2: Get credentials if needed
    if not has_credentials:
        if not get_google_credentials(env_path):
            print_error("Failed to configure credentials")
            sys.exit(1)
    
    # Step 3: Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies")
        sys.exit(1)
    
    # Step 4: Verify setup
    if not verify_google_setup():
        print_error("Setup verification failed")
        sys.exit(1)
    
    # Step 5: Test
    test_login()
    
    print("\n=== Google OAuth Login Setup Complete! ===\n")

if __name__ == '__main__':
    main()
