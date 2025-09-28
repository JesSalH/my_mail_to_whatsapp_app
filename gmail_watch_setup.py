import os
import pickle
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from datetime import datetime
import time

# If modifying these SCOPES, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailWatchSetup:
    def __init__(self, credentials_path, token_path, pubsub_topic, watch_response_path):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.pubsub_topic = pubsub_topic
        self.watch_response_path = watch_response_path  # Path to save watch response
        self.creds = None

    def authenticate(self):
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)

    def setup_watch(self):
        service = build('gmail', 'v1', credentials=self.creds)
        
        # Fetch the watched Gmail account email
        profile = service.users().getProfile(userId='me').execute()
        gmail_account = profile.get('emailAddress', 'Unknown')
        
        request = {
            'labelIds': ['INBOX'],
            'topicName': self.pubsub_topic
        }
        try:
            response = service.users().watch(userId='me', body=request).execute()
            
            # Save the response to a file for later verification
            with open(self.watch_response_path, 'w') as f:
                json.dump(response, f)
            
            # Convert expiration timestamp to human-readable date
            expiration_ms = response.get('expiration')
            expiration_time = datetime.fromtimestamp(int(expiration_ms) / 1000) if expiration_ms else "Unknown"
            
            print("Gmail watcher setup successful!")
            print(f"Watched Gmail account: {gmail_account}")
            print(f"Pub/Sub topic: {self.pubsub_topic}")
            print(f"Starting history ID: {response.get('historyId', 'Unknown')}")
            print(f"Expiration time: {expiration_time} (approximately 7 days from now)")
            print("Notifications will be sent to the topic upon inbox changes.")
            
            return response
        except Exception as e:
            print(f"Error setting up Gmail watcher: {str(e)}")
            print("Please check your Pub/Sub topic, permissions, or API configuration.")
            raise

    def verify_watch(self, history_id):
        service = build('gmail', 'v1', credentials=self.creds)
        
        print("\nVerification step: Send a test email to your watched account now, then press Enter to check history...")
        input()  # Wait for user to send email
        
        # Wait a short delay for the change to propagate
        time.sleep(10)
        
        try:
            response = service.users().history().list(userId='me', startHistoryId=history_id).execute()
            history = response.get('history', [])
            
            if history:
                print("Verification successful! Changes detected in history:")
                for item in history:
                    print(item)
            else:
                print("No changes detected in history. The watch may not be triggering. Try renewing the watch or checking filters.")
        except Exception as e:
            print(f"Error verifying watch: {str(e)}")

if __name__ == '__main__':
    # Load environment variables
    CREDENTIALS_PATH = 'credentials.json'
    TOKEN_PATH = 'token.pickle'
    WATCH_RESPONSE_PATH = 'watch_response.json'
    PUBSUB_TOPIC = os.environ.get('PUBSUB_TOPIC')
    if not PUBSUB_TOPIC:
        raise EnvironmentError("PUBSUB_TOPIC environment variable is not set. Please set it in your .env file.")

    gmail_watch = GmailWatchSetup(CREDENTIALS_PATH, TOKEN_PATH, PUBSUB_TOPIC, WATCH_RESPONSE_PATH)
    gmail_watch.authenticate()
    response = gmail_watch.setup_watch()
    gmail_watch.verify_watch(response.get('historyId'))