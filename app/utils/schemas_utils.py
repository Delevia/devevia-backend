from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator  
from typing import Optional
from fastapi import UploadFile
from ..enums import GenderEnum
from datetime import date
from fastapi import Form




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



# Define a Pydantic model for the request body
class PreRegisterRequest(BaseModel):
    full_name: str = Field(..., title="Full Name", description="The full name of the user")
    user_name: str = Field(..., title="Username", description="The username of the user")
    phone_number: str = Field(..., title="Phone Number", description="The phone number of the user")
    email: str = Field(..., title="Email", description="The email address of the user")
    password: str = Field(..., title="Password", description="The user's password")
    referral_code: str = Field(None, title="Referral Code", description="Optional referral code for the user")


class DriverPreRegisterRequest(BaseModel):
    full_name: str
    user_name: str
    phone_number: str
    email: EmailStr
    password: str



class DriverCompleteRegistrationRequest(BaseModel):
    phone_number: str = Form(...)
    license_number: str = Form(...)
    license_expiry: date = Form(...)
    years_of_experience: int = Form(...)
    referral_code: str = Form(...)
    vehicle_name: str = Form(...)
    vehicle_model: str = Form(...)
    vehicle_insurance_policy: str = Form(...)
    vehicle_exterior_color: str = Form(...)
    vehicle_interior_color: str = Form(...)
    nin_number: str = Form(...)