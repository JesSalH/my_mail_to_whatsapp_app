import subprocess
import time
import re
import sys
import os
import json
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get port from .env (default to 8081 if not set)
PORT = os.getenv('PORT', '8081')
NGROK_AUTHTOKEN = os.getenv('NGROK_AUTHTOKEN')

WATCH_RESPONSE_PATH = 'watch_response.json'  # Path to watch response file
WATCH_SCRIPT = 'gmail_watch_setup.py'  # Your Gmail watch setup script

def is_watch_active() -> bool:
    if not os.path.exists(WATCH_RESPONSE_PATH):
        return False
    
    with open(WATCH_RESPONSE_PATH, 'r') as f:
        response = json.load(f)
    
    expiration_ms = response.get('expiration')
    if not expiration_ms:
        return False
    
    # Convert expiration to datetime (expiration is in milliseconds since epoch)
    expiration_time = datetime.fromtimestamp(int(expiration_ms) / 1000)
    current_time = datetime.now()
    
    return expiration_time > current_time

def run_watch_setup() -> bool:
    print("Step 1: Setting up Gmail watch (running gmail_watch_setup.py in a new window)...")
    # Open a new console window for the watch setup
    setup_process = subprocess.Popen(
        f'start cmd /k python {WATCH_SCRIPT}',
        shell=True
    )
    
    # Wait for user to complete the setup (manual intervention if needed)
    input("Press Enter once the Gmail watch setup is complete in the new window...")
    
    # Check if watch_response.json was created/updated
    if os.path.exists(WATCH_RESPONSE_PATH):
        print("Gmail watch setup completed successfully.")
        return True
    else:
        print("Gmail watch setup failed (no watch_response.json found).")
        return False

def authenticate_ngrok():
    if not NGROK_AUTHTOKEN:
        raise ValueError("NGROK_AUTHTOKEN not found in .env file. Please add it and rerun.")
    print("Authenticating ngrok...")
    auth_process = subprocess.run(
        ['ngrok', 'authtoken', NGROK_AUTHTOKEN],
        capture_output=True,
        text=True
    )
    if auth_process.returncode != 0:
        raise RuntimeError(f"ngrok authentication failed: {auth_process.stderr}")
    print("ngrok authenticated successfully.")

def start_ngrok():
    authenticate_ngrok()  # Authenticate before starting the tunnel
    print("Step 2: Starting ngrok tunnel in a new window...")
    # Open a new console window for ngrok
    ngrok_process = subprocess.Popen(
        f'start cmd /k ngrok http {PORT}',
        shell=True
    )
    
    # Prompt user to copy the URL from the new window
    public_url = input("Enter the ngrok forwarding URL (e.g., https://random.ngrok-free.app) from the new console window: ")
    print(f"ngrok tunnel started at: {public_url}")
    return ngrok_process, public_url

def start_flask():
    print("Step 3: Starting Flask endpoint in a new console window...")
    # Open a new console window for Flask
    flask_process = subprocess.Popen(
        f'start cmd /k python gmail_push_notification_endpoint.py',
        shell=True
    )
    
    print("Flask endpoint started. Check the new window for logs.")
    return flask_process

if __name__ == '__main__':
    print("Starting orchestrator process...")
    
    # Step 1: Check and set up Gmail watch if needed
    print("Step 1: Checking Gmail watch status...")
    if not is_watch_active():
        print("Gmail watch is not active or expired.")
        if not run_watch_setup():
            print("Failed to set up Gmail watch. Exiting orchestrator.")
            sys.exit(1)
    else:
        print("Gmail watch is already active.")
        # Optionally print watch details here if needed

    # Step 2: Start ngrok
    ngrok_proc, public_url = start_ngrok()
    
    # Wait briefly
    time.sleep(5)
    
    # Step 3: Start Flask
    flask_proc = start_flask()
    
    # Keep the orchestrator running until interrupted
    try:
        input("Orchestrator running. Press Enter to shut down...")
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down...")
        # Note: Processes in new windows need manual closure or use taskkill if needed