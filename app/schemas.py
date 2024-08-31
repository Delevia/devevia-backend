from pydantic import BaseModel, EmailStr, Field, field_validator
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .models import User
from .enums import UserType as UserTypeEnum, UserStatusEnum
from typing import Optional
import re


# Initialize the CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



# Pydantic models for request bodies
class UserBase(BaseModel):
    full_name: str
    user_name: str
    phone_number: str
    email: EmailStr
    password: str
    address: str
    user_type: UserTypeEnum  # Enum field for user type
    user_status: Optional[UserStatusEnum] = UserStatusEnum.ACTIVE  # Default to ACTIVE



    class Config:
        orm_mode = True

# Rider creation schema
class RiderCreate(UserBase):
    pass  # Inherits all fields from UserBase

# Driver creation schema with license number
class DriverCreate(UserBase):
    license_number: str
    license_expiry: str
    years_of_experience: str  

# Schema for Requesting OTP
class PhoneNumberRequest(BaseModel):
    # Ensure the phone number is an integer within the range 10 to 15 digits long
    phone_number: int = Field(..., ge=1000000000, le=999999999999999)

    # Optional: Remove the regex check since it's already validated by the field type and range
    @field_validator('phone_number')
    def check_phone_number(cls, value):
        # Check if the length of the number is between 10 and 15 digits
        if not (10 <= len(str(value)) <= 15):
            raise ValueError("Phone number must be between 10 and 15 digits.")
        return value


# Schema for Verifying O T P
class OTPVerificationRequest(BaseModel):
    # Validates E.164 format for the phone number
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    # Ensures OTP is exactly 6 digits
    otp: str = Field(..., pattern=r'^\d{6}$')  

    @field_validator('otp')
    def check_otp(cls, value):
        # This validator checks if the OTP is exactly 6 digits long
        if len(value) != 6 or not value.isdigit():
            raise ValueError("OTP must be exactly 6 digits.")
        return value

    @field_validator('phone_number')
    def check_phone_number(cls, value):
        # Checks if the phone number matches the E.164 format
        if not re.match(r'^\+?[1-9]\d{1,14}$', value):
            raise ValueError("Invalid phone number format.")
        return value

   


# Utility function to hash passwords
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Function to create a new user
def create_user(db: Session, user: UserBase):
    db_user = User(
        full_name=user.full_name,
        user_name=user.user_name,
        phone_number=user.phone_number,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        address=user.address,
        user_type=user.user_type, 
        user_status=user.user_status

    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
