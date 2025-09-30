from flask import Flask, request, jsonify
import base64
import json
import pickle
import os
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from emailBroker.state_manager import StateManager
from events import event_bus, NEW_EMAILS_ARRIVED, NewEmailsArrivedEvent
from datetime import datetime

# SCOPES and paths
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.pickle'

app = Flask(__name__)
state = StateManager()  # persistent broker state

# ----------------------------
# Gmail helpers
# ----------------------------
def fetch_history(service, start_history_id):
    """Fetch Gmail history items since the last known historyId."""
    if not start_history_id:
        print("No previous historyId; skipping fetch.")
        return []
    history_response = service.users().history().list(
        userId='me',
        startHistoryId=start_history_id
    ).execute()
    return history_response.get('history', [])

def fetch_message(service, msg_id):
    """Retrieve a full Gmail message by ID."""
    return service.users().messages().get(
        userId='me',
        id=msg_id,
        format='full'
    ).execute()

def extract_subject(headers):
    """Extract the subject from email headers."""
    for h in headers:
        if h['name'] == 'Subject':
            return h['value']
    return 'No Subject'

def extract_body(payload):
    """Extract plain text body if available."""
    body = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                body = base64.urlsafe_b64decode(
                    part['body']['data']
                ).decode('utf-8')
                break
    return body

def process_history(service, history):
    """Process Gmail history items, store them as retrieved, and emit event."""
    new_email_ids = []  # Collect IDs of newly added emails
    for item in history:
        added_messages = item.get('messagesAdded', [])
        for added in added_messages:
            msg_id = added['message']['id']
            # Skip if we already have this message in state
            if state.get_message(msg_id):
                continue
            # Fetch full message
            msg = fetch_message(service, msg_id)
            headers = msg['payload']['headers']
            subject = extract_subject(headers)
            body = extract_body(msg['payload'])
            print(f"📩 Retrieved new email → Subject: {subject}")
            # Persist in state (retrieved, not delivered)
            state.add_retrieved_message(msg_id, subject, body)
            new_email_ids.append(msg_id)  # Track new email ID

    # If new emails were added, publish the new_emails_arrived event
    if new_email_ids:
        event_bus.publish(
            NEW_EMAILS_ARRIVED,
            NewEmailsArrivedEvent(email_ids=new_email_ids, timestamp=datetime.now())
        )
        print(f"📢 Published {NEW_EMAILS_ARRIVED} event with {len(new_email_ids)} email(s)")

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
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
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
    decoded_data = base64.b64decode(data).decode('utf-8')
    message_json = json.loads(decoded_data)
    print('🔔 Gmail push notification:', message_json)
    history_id = message_json.get('historyId')
    print(f"HistoryId from notification: {history_id}")
    last_history_id = state.get_last_history_id()
    print(f"Last stored historyId: {last_history_id if last_history_id else 'None (first run)'}")
    if history_id:
        service = get_gmail_service()
        history = fetch_history(service, last_history_id)
        if history:
            print(f"Processing {len(history)} history records...")
            process_history(service, history)
        else:
            print("No new history records found.")
        # Move forward our checkpoint
        state.set_last_history_id(history_id)
        print(f"Updated last_history_id → {history_id}")
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)