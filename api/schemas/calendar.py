from typing import Optional

from pydantic import BaseModel


class CalendarCreate(BaseModel):
    summary: str

class CalendarDeleteCriteria(BaseModel):
    summary: str