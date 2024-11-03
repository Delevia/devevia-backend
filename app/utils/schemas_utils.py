from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr



class OtpPhoneNumberRequest(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=15,
        pattern="^[0-9]+$"  # Use `pattern` instead of `regex`
    )


class UserProfileResponse(BaseModel):
    id: int
    user_name: str
    email: str
    phone_number: str
    address: Optional[str] = None
    user_status: Optional[str] = None
    user_type: Optional[str] = None

    class Config:
            # orm_mode = True
            exclude = {"created_at"}  # Ensure 'created_at' is excluded


class OtpSMSRequest(BaseModel):
    phone_number: str = Field(
        ...,
        pattern=r'^\+?\d{10,15}$',
        description="Phone number in international format, e.g., +23490126727 or 23490126727"
    )