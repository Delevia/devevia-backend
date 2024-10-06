from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from datetime import date
from ..database import get_async_db
from ..models import User, Rider, Driver, KYC, Admin
from ..schemas import KycCreate, AdminCreate, get_password_hash
from ..enums import PaymentMethodEnum
from ..utils.schemas_utils import UserProfileResponse
from ..utils.utils_dependencies_files import get_current_user
import logging
import os

router = APIRouter()

# Define the path to the 'app/router' directory where the log file will be stored
log_directory = 'app/router'

# Check if the directory exists; if not, create it
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Set up logging configuration to save the log file in the 'app/router' directory
logging.basicConfig(
    filename=os.path.join(log_directory, 'app.log'),  # Log file location
    level=logging.DEBUG,                              # Set log level to DEBUG for detailed output
    format='%(asctime)s - %(levelname)s - %(message)s'  # Log format
)

logger = logging.getLogger(__name__)

# Rider Signup Endpoint
@router.post("/signup/rider/", status_code=status.HTTP_201_CREATED)
async def signup_rider(
    full_name: str = Form(...),
    user_name: str = Form(...),
    phone_number: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    address: Optional[str] = Form(None),
    rider_photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    # Check if the user exists by phone number and email
    query = select(User).filter(User.phone_number == phone_number, User.email == email)
    existing_user = (await db.execute(query)).scalars().first()

    if existing_user:
        # Check if the user is already a rider
        query = select(Rider).filter(Rider.user_id == existing_user.id)
        existing_rider = (await db.execute(query)).scalars().first()
        if existing_rider:
            raise HTTPException(status_code=400, detail="User already registered as a Rider.")
    else:
        # If no existing user, create a new one
        hashed_password = get_password_hash(password)
        db_user = User(
            full_name=full_name,
            user_name=user_name,
            phone_number=phone_number,
            email=email,
            hashed_password=hashed_password,
            address=address,
            user_type="RIDER"
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

    # Save rider-specific data
    file_content = await rider_photo.read()
    db_rider = Rider(
        user_id=existing_user.id if existing_user else db_user.id,
        rider_photo=file_content,
    )
    db.add(db_rider)
    await db.commit()
    await db.refresh(db_rider)

    return {"message": "Rider registration successful"}

# Driver Signup Endpoint
@router.post("/signup/driver/", status_code=status.HTTP_201_CREATED)
async def signup_driver(
    full_name: str = Form(...),
    user_name: str = Form(...),
    phone_number: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    address: Optional[str] = Form(None),
    license_number: str = Form(...),
    license_expiry: date = Form(...),
    years_of_experience: int = Form(...),
    driver_photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    # Check if the license number already exists for another driver
    query = select(Driver).filter(Driver.license_number == license_number)
    existing_license = (await db.execute(query)).scalars().first()
    if existing_license:
        raise HTTPException(status_code=400, detail="License number already exists.")
    
    # Check if the user already exists by phone number
    query = select(User).filter(User.phone_number == phone_number)
    existing_user = (await db.execute(query)).scalars().first()

    if existing_user:
        # Check if the user is already registered as a Driver
        query = select(Driver).filter(Driver.user_id == existing_user.id)
        existing_driver = (await db.execute(query)).scalars().first()
        if existing_driver:
            raise HTTPException(status_code=400, detail="User already registered as a Driver.")

        # Check if the email matches with the existing user
        if existing_user.email != email:
            raise HTTPException(status_code=400, detail="Email does not match the existing user.")
    
    else:
        # Check if the email is already in use
        query = select(User).filter(User.email == email)
        existing_email_user = (await db.execute(query)).scalars().first()
        if existing_email_user:
            raise HTTPException(status_code=400, detail="Email already exists.")

        # Check if the username is already in use
        query = select(User).filter(User.user_name == user_name)
        existing_username = (await db.execute(query)).scalars().first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already exists.")

        # Hash the password and create the new User
        hashed_password = get_password_hash(password)
        db_user = User(
            full_name=full_name,
            user_name=user_name,
            phone_number=phone_number,
            email=email,
            hashed_password=hashed_password,
            address=address,
            user_type="DRIVER"
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

    # Save driver-specific data
    file_content = await driver_photo.read()
    db_driver = Driver(
        user_id=existing_user.id if existing_user else db_user.id,
        license_number=license_number,
        license_expiry=license_expiry,
        years_of_experience=years_of_experience,
        driver_photo=file_content
    )
    db.add(db_driver)
    await db.commit()
    await db.refresh(db_driver)

    # Update user type to DRIVER if the user already exists
    if existing_user:
        existing_user.user_type = "DRIVER"
        await db.commit()

    return {"message": "Driver registration successful"}

# Create a KYC
@router.post("/kyc/", status_code=status.HTTP_201_CREATED)
async def create_kyc(kyc: KycCreate, db: AsyncSession = Depends(get_async_db)) -> Any:
    query = select(KYC).filter(KYC.user_id == kyc.user_id)
    existing_kyc = (await db.execute(query)).scalars().first()
    if existing_kyc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="KYC record already exists for this user."
        )

    query = select(KYC).filter(KYC.identity_number == kyc.identity_number)
    existing_identity = (await db.execute(query)).scalars().first()
    if existing_identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identity number already exists."
        )

    new_kyc = KYC(
        user_id=kyc.user_id,
        identity_number=kyc.identity_number
    )
    db.add(new_kyc)
    await db.commit()
    await db.refresh(new_kyc)

    return {"message": "KYC record created successfully", "kyc_id": new_kyc.kyc_id}


# Create Admin Endpoint
@router.post("/admin/", status_code=status.HTTP_201_CREATED)
async def create_admin(admin: AdminCreate, db: AsyncSession = Depends(get_async_db)) -> Any:
    query = select(User).filter(User.id == admin.user_id)
    user = (await db.execute(query)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_admin = Admin(
        user_id=admin.user_id,
        department=admin.department,
        access_level=admin.access_level
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)

    return {"message": "Admin record created successfully", "admin_id": new_admin.id}


# User Profile
@router.get("/profile/")
async def get_user_profile(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    # Log fetching process
    query = select(User).filter(User.id == current_user.id)
    user = (await db.execute(query)).scalars().first()
    logger.debug(f"Fetched user from DB: {user}")
    
    if not user:
        logger.error("User not found")
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build response manually, excluding 'created_at'
    user_profile_response = UserProfileResponse(
        id=user.id,
        user_name=user.user_name,
        email=user.email,
        phone_number=user.phone_number,
        full_name=user.full_name,
        address=user.address,
        user_type=user.user_type,
        user_status=user.user_status
    )
    return user_profile_response

