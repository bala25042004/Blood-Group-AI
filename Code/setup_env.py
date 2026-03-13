import secrets
import os

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
secret_key = secrets.token_hex(24)

env_content = f"""# Flask Secret Key
FLASK_SECRET_KEY={secret_key}

# Twilio Credentials (Get from: https://www.twilio.com/console)
# Set these to enable real phone SMS
TWILIO_ACCOUNT_SID=AC_YOUR_TWILIO_SID
TWILIO_AUTH_TOKEN=YOUR_AUTH_TOKEN
TWILIO_PHONE_NUMBER=YOUR_TWILIO_NUMBER

# Google OAuth Credentials (Get from: https://console.cloud.google.com/)
# Set these to enable Google Login
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_SECRET_KEY
"""

with open(env_path, 'w') as f:
    f.write(env_content)
print(f"Created .env file at {env_path}")
