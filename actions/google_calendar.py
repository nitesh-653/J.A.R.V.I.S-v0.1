"""
google_calendar.py — Mark XXXIX Google Calendar Voice Control
Read and create calendar events via Google Calendar API.
Requires: google-auth-oauthlib, google-api-python-client
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    _GCAL_OK = True
except ImportError:
    _GCAL_OK = False

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _token_path() -> Path:
    return _base_dir() / "config" / "gcal_token.json"

def _creds_path() -> Path:
    return _base_dir() / "config" / "gcal_credentials.json"

def _get_service():
    if not _GCAL_OK:
        raise RuntimeError(
            "Google Calendar libraries not installed. Run: "
            "pip install google-auth-oauthlib google-api-python-client"
        )
    creds = None
    token = _token_path()
    creds_file = _creds_path()
    if not creds_file.exists():
        raise RuntimeError(
            "Google Calendar credentials not found. "
            "Download OAuth2 credentials from Google Cloud Console and save as "
            "config/gcal_credentials.json"
        )
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)

def _parse_datetime(date_str: str, time_str: str = "") -> str:
    from datetime import date
    now = datetime.now()
    if date_str.lower() in ("today", ""):
        dt = now.date()
    elif date_str.lower() == "tomorrow":
        dt = (now + timedelta(days=1)).date()
    elif date_str.lower().startswith("next "):
        days = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,
                "friday":4,"saturday":5,"sunday":6}
        day_name = date_str.lower().replace("next ", "")
        target = days.get(day_name, 0)
        current = now.weekday()
        delta = (target - current + 7) % 7 or 7
        dt = (now + timedelta(days=delta)).date()
    else:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            dt = now.date()
    if time_str:
        try:
            t = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            try:
                t = datetime.strptime(time_str, "%I:%M %p").time()
            except ValueError:
                t = datetime.strptime("09:00", "%H:%M").time()
        return datetime.combine(dt, t).isoformat()
    return dt.isoformat()

def google_calendar(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    action = parameters.get("action", "list").lower().strip()
    try:
        service = _get_service()
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Google Calendar connection failed: {e}"

    try:
        if action in ("list", "events", "today", "tomorrow", "what"):
            date_str = parameters.get("date", "today")
            if "tomorrow" in action:
                date_str = "tomorrow"
            start_iso = _parse_datetime(date_str)
            start_dt  = datetime.fromisoformat(start_iso)
            end_dt    = start_dt + timedelta(days=1)
            events_result = service.events().list(
                calendarId="primary",
                timeMin=start_dt.isoformat() + "Z" if "T" in start_iso else start_dt.isoformat() + "T00:00:00Z",
                timeMax=end_dt.isoformat() + "Z" if "T" in end_dt.isoformat() else end_dt.isoformat() + "T00:00:00Z",
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events = events_result.get("items", [])
            if not events:
                return f"No events found for {date_str}, sir."
            lines = [f"Here are your events for {date_str}, sir:"]
            for e in events:
                start = e["start"].get("dateTime", e["start"].get("date", ""))
                if "T" in start:
                    t = datetime.fromisoformat(start.replace("Z","")).strftime("%I:%M %p")
                else:
                    t = "All day"
                lines.append(f"  • {t} — {e.get('summary', 'No title')}")
            return "\n".join(lines)

        elif action in ("create", "schedule", "add"):
            title     = parameters.get("title", parameters.get("summary", "Meeting")).strip()
            date_str  = parameters.get("date", "today")
            time_str  = parameters.get("time", "09:00")
            duration  = int(parameters.get("duration_minutes", 60))
            attendees = parameters.get("attendees", "")
            start_iso = _parse_datetime(date_str, time_str)
            start_dt  = datetime.fromisoformat(start_iso)
            end_dt    = start_dt + timedelta(minutes=duration)
            event_body: dict = {
                "summary": title,
                "start":   {"dateTime": start_dt.isoformat(), "timeZone": "local"},
                "end":     {"dateTime": end_dt.isoformat(),   "timeZone": "local"},
            }
            if attendees:
                emails = [a.strip() for a in attendees.split(",") if "@" in a]
                if emails:
                    event_body["attendees"] = [{"email": em} for em in emails]
            created = service.events().insert(
                calendarId="primary", body=event_body
            ).execute()
            if player:
                player.write_log(f"[Calendar] ✅ Created: {title}")
            friendly = start_dt.strftime("%B %d at %I:%M %p")
            return f"Event '{title}' scheduled for {friendly}, sir."

        elif action in ("delete", "cancel"):
            title = parameters.get("title", "").strip()
            if not title:
                return "Please specify which event to cancel."
            now = datetime.utcnow().isoformat() + "Z"
            results = service.events().list(
                calendarId="primary", timeMin=now,
                maxResults=20, singleEvents=True, orderBy="startTime",
                q=title,
            ).execute()
            items = results.get("items", [])
            if not items:
                return f"No upcoming event matching '{title}' found."
            service.events().delete(
                calendarId="primary", eventId=items[0]["id"]
            ).execute()
            return f"Cancelled '{items[0].get('summary', title)}', sir."

        else:
            return f"Unknown calendar action: '{action}'. Try list, create, or cancel."

    except Exception as e:
        return f"Calendar error: {e}"
