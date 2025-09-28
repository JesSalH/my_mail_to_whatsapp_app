from flask import Flask, request, jsonify
import base64
import json
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os

# SCOPES and paths (match your watcher file)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.pickle'
LAST_HISTORY_FILE = 'last_history_id.txt'  # File to store last historyId

app = Flask(__name__)

def load_last_history_id():
    if os.path.exists(LAST_HISTORY_FILE):
        with open(LAST_HISTORY_FILE, 'r') as f:
            return f.read().strip()
    return None  # If no file, first run won't fetch history

def save_last_history_id(history_id):
    with open(LAST_HISTORY_FILE, 'w') as f:
        f.write(str(history_id))

def fetch_history(service, start_history_id):
    if not start_history_id:
        print("No previous historyId; skipping fetch.")
        return []
    history_response = service.users().history().list(userId='me', startHistoryId=start_history_id).execute()
    return history_response.get('history', [])

def fetch_message(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    return msg

def extract_subject(headers):
    for h in headers:
        if h['name'] == 'Subject':
            return h['value']
    return 'No Subject'

def extract_body(payload):
    body = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                break
    return body

def process_history(service, history):
    for item in history:
        added_messages = item.get('messagesAdded', [])
        for added in added_messages:
            msg_id = added['message']['id']
            msg = fetch_message(service, msg_id)
            headers = msg['payload']['headers']
            subject = extract_subject(headers)
            body = extract_body(msg['payload'])
            print(f"New Email Details - Subject: {subject}, Body: {body}")

def get_gmail_service():
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

@app.route('/gmail_push', methods=['POST'])
def gmail_push():
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
    print('Received Gmail push notification:', message_json)
    
    history_id = message_json.get('historyId')
    print(f"Received historyId: {history_id}")
    
    last_history_id = load_last_history_id()
    print(f"Last stored historyId: {last_history_id if last_history_id else 'None (first run)'}")
    
    if history_id:
        service = get_gmail_service()
        history = fetch_history(service, last_history_id)
        found_ids = [item['id'] for item in history]
        print(f"Found history IDs after last stored: {found_ids if found_ids else 'None'}")
        
        process_history(service, history)
        
        print(f"Updating stored historyId to latest: {history_id}")
        save_last_history_id(history_id)
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)