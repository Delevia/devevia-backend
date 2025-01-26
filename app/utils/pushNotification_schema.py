from pydantic import BaseModel
from typing import List, Optional

class NotificationRequest(BaseModel):
    title: str
    message: str
    external_ids: Optional[List[str]] = None  # Specific users (External IDs)
    segment: Optional[str] = None            # Target user segment (optional)


class DriverCoordinateRequest(BaseModel):
    driver_id: int
    latitude: float
    longitude: float