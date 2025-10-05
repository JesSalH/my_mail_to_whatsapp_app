from flask import Flask, request, jsonify
import base64
import json
import pickle
import os
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import time

# --- Project imports ---
from emailBroker.state_manager import StateManager
from events.events import NewEmailsArrivedEvent  # fixed import path to match actual event module

# ----------------------------
# Gmail API setup
# ----------------------------
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.pickle'

app = Flask(__name__)
state = StateManager()  # persistent broker state
send_conn = None  # will be injected by run_app()


# ----------------------------
# Gmail helpers
# ----------------------------
def fetch_history(service, start_history_id):
    """Fetch Gmail history items since the last known historyId."""
    if not start_history_id:
        print("⚠️ No previous historyId; skipping fetch.")
        return []
    try:
        history_response = service.users().history().list(
            userId='me',
            startHistoryId=start_history_id
        ).execute()
        return history_response.get('history', [])
    except Exception as e:
        print(f"❌ Error fetching Gmail history: {e}")
        return []


def fetch_message(service, msg_id):
    """Retrieve a full Gmail message by ID."""
    try:
        return service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full'
        ).execute()
    except Exception as e:
        print(f"❌ Failed to fetch message {msg_id}: {e}")
        return None


def extract_subject(headers):
    """Extract the subject from email headers."""
    for h in headers:
        if h['name'].lower() == 'subject':
            return h['value']
    return '(No Subject)'


def extract_body(payload):
    """Extract plain text body if available."""
    body = ''
    try:
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
        elif 'body' in payload and 'data' in payload['body']:
            # Fallback: message might not have parts (simple emails)
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    except Exception as e:
        print(f"⚠️ Error decoding body: {e}")
    return body


def process_history(service, history, send_conn):
    """Process Gmail history items, store them as retrieved, and send event via pipe."""
    new_email_ids = []  # collect IDs of newly added emails

    for item in history:
        added_messages = item.get('messagesAdded', [])
        for added in added_messages:
            msg_id = added['message']['id']

            # Skip if message already exists in state
            if state.get_message(msg_id):
                print(f"↩️ Skipping already known message: {msg_id}")
                continue

            # Fetch the message and extract content
            msg = fetch_message(service, msg_id)
            if not msg:
                continue

            headers = msg['payload'].get('headers', [])
            subject = extract_subject(headers)
            body = extract_body(msg['payload'])

            print(f"📩 Retrieved new email → ID: {msg_id} | Subject: {subject[:60]}")

            # Store in persistent state as 'retrieved'
            state.add_retrieved_message(msg_id, subject, body)

            # 🔧 Add explicit save flush
            state._save_state()

            new_email_ids.append(msg_id)

    # Emit the event if any new emails were added
    if new_email_ids:
        
        # ✅ Small delay to ensure file writes finish before Orchestrator reads
        time.sleep(1)

        event = NewEmailsArrivedEvent(email_ids=new_email_ids, timestamp=datetime.now())
        send_conn.send(event)
        print(f"📢 Sent NEW_EMAILS_ARRIVED event with {len(new_email_ids)} email(s): {new_email_ids}")
    else:
        print("ℹ️ No new emails found to process.")


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)


# ----------------------------
# Flask route
# ----------------------------
@app.route('/gmail_push', methods=['POST'])
def gmail_push():
    """Endpoint that receives Pub/Sub push notifications from Gmail."""
    envelope = request.get_json()
    if not envelope:
        return 'Bad Request: no JSON body', 400

    pubsub_message = envelope.get('message')
    if not pubsub_message:
        return 'Bad Request: no message field', 400

    data = pubsub_message.get('data')
    if not data:
        return 'Bad Request: no data field', 400

    # Decode the Pub/Sub message payload
    decoded_data = base64.urlsafe_b64decode(data).decode('utf-8')
    message_json = json.loads(decoded_data)
    print('🔔 Gmail push notification received:', message_json)

    history_id = message_json.get('historyId')
    print(f"HistoryId from notification: {history_id}")

    last_history_id = state.get_last_history_id()
    print(f"Last stored historyId: {last_history_id if last_history_id else 'None (first run)'}")

    if history_id:
        service = get_gmail_service()
        history = fetch_history(service, last_history_id)

        if history:
            print(f"Processing {len(history)} history record(s)...")
            process_history(service, history, send_conn)
        else:
            print("No new history records found — nothing to process.")

        # Update the history checkpoint in state
        state.set_last_history_id(history_id)
        print(f"✅ Updated last_history_id → {history_id}")

    return jsonify({'status': 'success'})


def run_app(child_conn):
    """Run Flask server in multiprocessing context, injecting the communication pipe."""
    global send_conn
    send_conn = child_conn  # Make pipe sender globally accessible
    print("✅ Flask Gmail Push Endpoint started — awaiting Gmail notifications...")
    app.run(host='0.0.0.0', port=8081, debug=True, use_reloader=False)
