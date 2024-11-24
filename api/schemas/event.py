# schemas/event.py

from typing import Optional

from pydantic import BaseModel


class EventCreate(BaseModel):
    summary: str
    start: str
    end: str

class EventDeleteCriteria(BaseModel):
    summary: str
    date: str # Accept only the date in YYYY-MM-DD format

class EventSearchCriteria(BaseModel):
    date: str # Accept only the date in YYYY-MM-DD format

class EventMoveCriteria(BaseModel):
    summary: str
    date: str  # Accept only the date in YYYY-MM-DD format
    new_start: str

class EventMoveToCalendarCriteria(BaseModel):
    summary: str
    date: str  # Accept only the date in YYYY-MM-DD format
    new_calendar_summary: str