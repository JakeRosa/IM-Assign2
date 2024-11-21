import datetime
import os.path
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi import Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from schemas.calendar import CalendarCreate, CalendarDeleteCriteria
from schemas.event import (EventCreate, EventDeleteCriteria, EventMoveCriteria,
                           EventMoveToCalendarCriteria)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/calendar"]

def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def normalize_string(s):
    return re.sub(r'\W+', '', s).lower()

@app.get("/events")
def list_all_events():
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No upcoming events found."}

        return [
            {"start": event["start"].get("dateTime", event["start"].get("date")), "summary": event["summary"]}
            for event in events
        ]

    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.post("/events")
async def create_event(event: EventCreate):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        event_body = {
            'summary': event.summary,
            'location': event.location,
            'description': event.description,
            'start': {
                'dateTime': event.start,
                'timeZone': 'Europe/Lisbon',
            },
            'end': {
                'dateTime': event.end,
                'timeZone': 'Europe/Lisbon',
            },
        }
        created_event = service.events().insert(calendarId='primary', body=event_body).execute()
        return {"message": "Event created", "event": created_event}
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.delete("/events")
async def delete_event(criteria: EventDeleteCriteria):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No events found."}

        # Normalize the criteria summary
        normalized_criteria_summary = normalize_string(criteria.summary)

        # Find the event to delete based on criteria
        event_to_delete = None
        for event in events:
            event_start_date = event["start"].get("dateTime", event["start"].get("date")).split("T")[0]
            normalized_event_summary = normalize_string(event["summary"])
            if normalized_event_summary == normalized_criteria_summary and event_start_date == criteria.date:
                event_to_delete = event
                event_to_delete["start"] = event_start_date
                break
        
        if not event_to_delete:
            return {"message": "No matching event found."}

        # Delete the event
        service.events().delete(calendarId='primary', eventId=event_to_delete["id"]).execute()
        return {"message": "Event deleted", "event": event_to_delete}

    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.get("/events/day")
async def get_events_by_day(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        start_of_day = f"{date}T00:00:00Z"
        end_of_day = f"{date}T23:59:59Z"
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No events found for this day."}

        return [
            {
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "summary": event["summary"],
                "description": event.get("description"),
                "location": event.get("location")
            }
            for event in events
        ]

    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")

@app.get("/holidays")
async def get_portugal_holidays():
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        next_year = (datetime.datetime.utcnow() + datetime.timedelta(days=365)).isoformat() + "Z"
        events_result = (
            service.events()
            .list(
                calendarId="pt.portuguese#holiday@group.v.calendar.google.com",
                timeMin=now,
                timeMax=next_year,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No holidays found for this period."}

        return [
            {
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "summary": event["summary"],
                "description": event.get("description", "")
            }
            for event in events
        ]
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.put("/events/move")
async def move_event(criteria: EventMoveCriteria):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No events found."}
        
        # Find the event to move based on criteria
        event_to_move = None
        for event in events:
            event_start_date = event["start"].get("dateTime", event["start"].get("date")).split("T")[0]
            if event["summary"] == criteria.summary and event_start_date == criteria.date:
                event_to_move = event
                break

        if not event_to_move:
            return {"message": "No matching event found."}

        # Update the event fields
        event_to_move['start'] = {'dateTime': criteria.new_start, 'timeZone': 'Europe/Lisbon'}
        event_to_move['end'] = {'dateTime': criteria.new_end, 'timeZone': 'Europe/Lisbon'}

        # Update the event
        updated_event = service.events().update(calendarId='primary', eventId=event_to_move["id"], body=event_to_move).execute()
        return {"message": "Event moved", "event": updated_event}
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")

@app.get("/birthdays")
async def get_birthdays():
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        next_year = (datetime.datetime.utcnow() + datetime.timedelta(days=365)).isoformat() + "Z"
        events_result = (
            service.events()
            .list(
                calendarId="addressbook#contacts@group.v.calendar.google.com",
                timeMin=now,
                timeMax=next_year,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No birthdays found for this period."}

        return [
            {
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "summary": event["summary"],
                "description": event.get("description", "")
            }
            for event in events
        ]
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.post("/calendars")
async def create_calendar(calendar: CalendarCreate):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        calendar_body = {
            'summary': calendar.summary,
            'timeZone': 'Europe/Lisbon',
        }
        created_calendar = service.calendars().insert(body=calendar_body).execute()
        return {"message": "Calendar created", "calendar": created_calendar}
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")

@app.delete("/calendars")
async def delete_calendar(criteria: CalendarDeleteCriteria):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        # List all calendars to find the one to delete
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        # Find the calendar to delete based on criteria
        calendar_to_delete = None
        for calendar in calendars:
            if calendar["summary"] == criteria.summary:
                calendar_to_delete = calendar
                break

        if not calendar_to_delete:
            return {"message": "No matching calendar found."}

        # Delete the calendar
        service.calendars().delete(calendarId=calendar_to_delete["id"]).execute()
        return {"message": "Calendar deleted", "calendar": calendar_to_delete}

    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")

@app.put("/events/move-to-calendar")
async def move_event_to_calendar(criteria: EventMoveToCalendarCriteria):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No events found."}
        
        # Find the event to move based on criteria
        event_to_move = None
        for event in events:
            event_start_date = event["start"].get("dateTime", event["start"].get("date")).split("T")[0]
            if event["summary"] == criteria.summary and event_start_date == criteria.date:
                event_to_move = event
                break

        if not event_to_move:
            return {"message": "No matching event found."}

        # List all calendars to find the new calendar
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        # Find the new calendar based on criteria
        new_calendar = None
        for calendar in calendars:
            if calendar["summary"] == criteria.new_calendar_summary:
                new_calendar = calendar
                break

        if not new_calendar:
            return {"message": "No matching calendar found."}

        # Move the event to the new calendar
        moved_event = service.events().move(calendarId='primary', eventId=event_to_move["id"], destination=new_calendar["id"]).execute()
        return {"message": "Event moved to new calendar", "event": moved_event}
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")
    
@app.get("/events/calendar")
async def get_events_in_calendar(calendar_summary: str = Query(..., description="Summary of the calendar")):
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        # List all calendars to find the one to get events from
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        # Find the calendar based on criteria
        calendar_to_use = None
        for calendar in calendars:
            if calendar["summary"] == calendar_summary:
                calendar_to_use = calendar
                break

        if not calendar_to_use:
            return {"message": "No matching calendar found."}

        # Get events from the calendar
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId=calendar_to_use["id"],
                timeMin=now,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {"message": "No events found in this calendar."}

        return [
            {
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "summary": event["summary"],
                "description": event.get("description"),
                "location": event.get("location")
            }
            for event in events
        ]
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)