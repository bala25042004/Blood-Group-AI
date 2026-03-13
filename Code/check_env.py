import os
from dotenv import load_dotenv

load_dotenv()

cid = os.getenv('GOOGLE_CLIENT_ID')
secret = os.getenv('GOOGLE_CLIENT_SECRET')

print("--- Environment Check ---")
if cid:
    print(f"GOOGLE_CLIENT_ID: {cid[:10]}...{cid[-10:]} (Total length: {len(cid)})")
else:
    print("GOOGLE_CLIENT_ID: NOT FOUND")

if secret:
    print(f"GOOGLE_CLIENT_SECRET: {secret[:5]}...{secret[-5:]} (Total length: {len(secret)})")
else:
    print("GOOGLE_CLIENT_SECRET: NOT FOUND")

print("\n--- Common Fixes ---")
print("1. Ensure GOOGLE_CLIENT_ID is for 'Web Application', not 'Desktop App'.")
print("2. Ensure GOOGLE_CLIENT_SECRET does NOT contain project number.")
print("3. Ensure Authorized Redirect URI is: http://localhost:5000/google_authorized (or http://127.0.0.1:5000/...)")
