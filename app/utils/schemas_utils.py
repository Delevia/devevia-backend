from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator  
from typing import Optional
from fastapi import UploadFile
from ..enums import GenderEnum


class OtpPhoneNumberRequest(BaseModel):
    phone_number: str = Field(
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

class RiderProfileUpdate(BaseModel):
    rider_id: int
    gender: Optional[GenderEnum]
    address: Optional[str]
    nin: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]
    profile_photo: Optional[str]  # file path
    nin_photo: Optional[str]  # file path

    @field_validator('nin')
    def validate_nin(cls, v):
        if v and len(v) != 11:
            raise ValueError('NIN must be exactly 11 characters')
        return v

    class Config:
        from_attributes = True


class RiderProfile(BaseModel):
    rider_id: int
    gender: Optional[str] = None
    address: Optional[str] = None
    nin: Optional[str] = None
    profile_photo: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None

    class Config:
        from_attributes = True




