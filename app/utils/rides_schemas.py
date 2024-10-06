from typing import Optional
from pydantic import BaseModel, Field, model_validator, constr
from datetime import datetime
from ..enums import RideStatusEnum, PaymentMethodEnum



# Define the RideRequest schema
class RideRequest(BaseModel):
    pickup_location: str
    dropoff_location: str
    booking_for: str = Field(..., pattern="^(self|other)$")  # Use 'pattern' instead of 'regex'
    recipient_phone_number: Optional[str] = Field(
        None, min_length=10, max_length=15, pattern=r"^\d{10,15}$"  # Use 'pattern' here as well
    )

    class Config:
        schema_extra = {
            "example": {
                "pickup_location": "123 Main St",
                "dropoff_location": "456 Elm St",
                "booking_for": "other",
                "recipient_phone_number": "5555555555"
            }
        }


# Model for the response after ride booking
class RideResponse(BaseModel):
    ride_id: int
    rider_id: int
    pickup_location: str
    dropoff_location: str
    estimated_price: float
    status: RideStatusEnum
    requested_time: datetime
    assigned_driver_id: Optional[int] = None  # Initially no driver assigned


# Pydantic schema for rating request
class RatingRequest(BaseModel):
    ride_id: int
    driver_id: int
    rating: float  # e.g., 1-5 stars
    comment: str = None


# Response after the ride has ended
class RideCompletionResponse(BaseModel):
    ride_id: int
    rider_id: int
    driver_id: int
    pickup_location: str
    dropoff_location: str
    final_fare: float  # The final fare after ride completion
    status: RideStatusEnum  # e.g., COMPLETED
    requested_time: datetime
    completed_time: datetime  # Time when the ride was completed
    rider_rating: Optional[float] = None  # Rating given by the rider to the driver
    driver_rating: Optional[float] = None  # Rating given by the driver to the rider



# Payment Method Schema
class PaymentMethodRequest(BaseModel):
    payment_method: PaymentMethodEnum
    card_number: Optional[str]  # Optional, required if card is chosen
    expiry_date: Optional[str]  # Optional, required if card is chosen
    token: Optional[str]
    is_default: Optional[bool] = Field(False)

    @model_validator(mode="before")
    def validate_payment_method(cls, values):
        payment_method = values.get("payment_method")

        if payment_method in { PaymentMethodEnum.DEBIT_CARD}:
            card_number = values.get("card_number")
            expiry_date = values.get("expiry_date")
            
            if not card_number or not expiry_date:
                raise ValueError("Card number and expiry date are required for card payments")
        return values

    class Config:
        orm_mode = True


