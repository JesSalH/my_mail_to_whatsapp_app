import subprocess
import time
import re
import sys
import os
import json
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv
from emailBroker import EmailBroker, StateManager, EmailSummarizer, MockNotifier, ConsoleNotifier
from emailBroker.llm_providers import OpenAILLM
from multiprocessing import Pipe, Process
import threading
from events import NewEmailsArrivedEvent  # Retained for event class reference in handler and listener

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

def start_flask(child_conn):
    """Start Flask as a multiprocessing Process and pass the pipe."""
    from gmail_push_notification_endpoint import run_app  # Import the run function (we'll define this in the Flask script later)
    flask_process = Process(target=run_app, args=(child_conn,))
    flask_process.start()
    return flask_process

def handle_new_emails(event: NewEmailsArrivedEvent, broker: EmailBroker):
    count = len(event.email_ids)
    print(f"DEBUG: Calculated new count from event: {count}")
    print(f"DEBUG: Event-specific email IDs: {event.email_ids}")
    broker.notify_new_messages(email_ids=event.email_ids)
    print("DEBUG: Number of new emails notified to user.")

    print("---------- DEBUG: Proceeding to deliver summaries for new emails... ----------")
    broker.deliver_new_summaries(email_ids=event.email_ids)

def listen_for_events(recv_pipe, broker):
    """Listener thread to receive events from the pipe and handle them."""
    while True:
        try:
            event_data = recv_pipe.recv()  # Blocks until data is received
            print("DEBUG: Received data from pipe:", type(event_data))  # Debug: Log received data type
            if isinstance(event_data, NewEmailsArrivedEvent):
                print("DEBUG: Event matches NewEmailsArrivedEvent - triggering handler")  # Debug: Confirm match
                handle_new_emails(event_data, broker)
            else:
                print("DEBUG: Received data does not match NewEmailsArrivedEvent")  # Debug: Mismatch case
        except EOFError:
            print("DEBUG: Pipe closed - exiting listener")  # Debug: Shutdown confirmation
            break
        except Exception as e:
            print("DEBUG: Exception in listener:", str(e))  # Debug: Catch any other errors

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
  
    # Step 2: Start ngrok and obtain public URL
    ngrok_proc, public_url = start_ngrok()
    
    # Step 3: Create a pipe for inter-process communication (Flask to orchestrator)
    parent_conn, child_conn = Pipe(duplex=False)  # Unidirectional: child -> parent
  
    # Step 4: Wait briefly to ensure ngrok is ready
    time.sleep(4)
  
    # Step 5: Start Flask as a child process, passing the sending end of the pipe
    flask_proc = start_flask(child_conn)
  
    # Step 6: Initialize EmailBroker components (state, summarizer, broker)
    state = StateManager()
    summarizer = EmailSummarizer(llm_backend=OpenAILLM(), state=state)
    broker = EmailBroker(state=state, notifier=ConsoleNotifier(), summarizer=summarizer)
    
    # Step 7: Start the background listener thread to receive and handle events from the pipe
    listener_thread = threading.Thread(target=listen_for_events, args=(parent_conn, broker), daemon=True)
    listener_thread.start()
  
    # Step 8: Keep the orchestrator running until user interrupts (e.g., press Enter)
    try:
        input("Orchestrator running. Press Enter to shut down...")
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down...")
        # Note: ngrok process (in separate window) may need manual closure or use taskkill if needed
        # Step 9: Close the pipe connections to signal end of communication
        parent_conn.close()
        child_conn.close()
       
        # Step 10: Terminate and join the Flask process for clean shutdown
        if flask_proc.is_alive():
            flask_proc.terminate()
            flask_proc.join()
       
        # Step 11: Join the listener thread (it will exit via EOFError after pipe closes)
        listener_thread.join()