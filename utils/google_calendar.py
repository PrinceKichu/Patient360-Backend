import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes for accessing calendar events and creating meet links
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    """Authorize and return the Google Calendar service."""
    creds = None
    token_path = 'token.json'

    # Load token if it exists
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    else:
        # First-time login: trigger browser-based OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=8000, redirect_uri_trailing_slash=False)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service


def create_google_meet_event(summary, description, start_time, end_time, timezone='Asia/Kolkata'):
    """Create a Google Calendar event with a Google Meet link."""
    service = get_calendar_service()

    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time,
            'timeZone': timezone,
        },
        'conferenceData': {
            'createRequest': {
                'requestId': f"meet-{datetime.datetime.utcnow().timestamp()}",
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        }
    }

    event_result = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1
    ).execute()

    return event_result.get('hangoutLink')
