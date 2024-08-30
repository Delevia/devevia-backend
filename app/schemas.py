from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .models import User
from .enums import UserType as UserTypeEnum, UserStatusEnum
from typing import Optional


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
