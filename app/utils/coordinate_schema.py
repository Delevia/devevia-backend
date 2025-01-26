from pydantic import BaseModel, Field
from typing import List

class DriverCoordinateUpdate(BaseModel):
    driver_id: int = Field(..., description="The ID of the driver")
    latitude: float = Field(..., description="The new latitude of the driver")
    longitude: float = Field(..., description="The new longitude of the driver")

class CoordinatesUpdateRequest(BaseModel):
    driver_coordinates: List[DriverCoordinateUpdate] = Field(
        ..., description="List of driver coordinates to update"
    )
