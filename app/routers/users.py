from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
from typing import Any, Optional, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta, date
from ..database import get_async_db
from ..models import User, Rider, Driver, KYC, Admin, Wallet, Referral
from ..schemas import KycCreate, AdminCreate, get_password_hash
from ..utils.schemas_utils import RiderProfileUpdate, RiderProfile
from ..utils.utils_dependencies_files import get_current_user, generate_hashed_referral_code
from ..utils.wallet_utilitity_functions import generate_global_unique_account_number
import logging
import os
from ..utils.otp import generate_otp, OTPVerification, generate_otp_expiration
import httpx
from io import BytesIO
import base64
import random
from sqlalchemy.future import select
from fastapi import HTTPException
from ..enums import UserType, GenderEnum
from pydantic import BaseModel, Field, EmailStr, ValidationError
from app.utils.security import hash_password
import aiofiles


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




# Define a Pydantic model for the request body
class PreRegisterRequest(BaseModel):
    full_name: str = Field(..., title="Full Name", description="The full name of the user")
    user_name: str = Field(..., title="Username", description="The username of the user")
    phone_number: str = Field(..., title="Phone Number", description="The phone number of the user")
    email: str = Field(..., title="Email", description="The email address of the user")
    password: str = Field(..., title="Password", description="The user's password")
    referral_code: str = Field(None, title="Referral Code", description="Optional referral code for the user")

# Rider Pre Registration
@router.post("/pre-register/rider/", status_code=status.HTTP_200_OK)
async def pre_register_rider(
    request: PreRegisterRequest,
    db: AsyncSession = Depends(get_async_db)
):
    # Extract data from the request
    full_name = request.full_name
    user_name = request.user_name
    phone_number = request.phone_number
    email = request.email
    password = request.password
    referral_code = request.referral_code

    # Generate OTP and expiration time
    otp_code = generate_otp()
    expiration_time = generate_otp_expiration()

    # Store the user data along with the OTP in the database
    async with db as session:
        otp_entry = OTPVerification(
            full_name=full_name,
            user_name=user_name,
            phone_number=phone_number,
            email=email,
            otp_code=otp_code,
            expires_at=expiration_time,
            is_verified=False,
            hashed_password=hash_password(password),  # Hash the password for storage
            referral_code=referral_code
        )
        session.add(otp_entry)
        await session.commit()
        await session.refresh(otp_entry)  # Refresh the entry to get the updated data from the database

    # Uncomment the following lines if email and SMS OTP sending functionality is implemented
    # # Send OTP via email
    # async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
    #     email_response = await client.post(
    #         "/auth/send-otp-email", params={"to_email": email, "otp_code": otp_code}
    #     )
    #     if email_response.status_code != 200:
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP email.")

    # # Send OTP via SMS
    # async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
    #     sms_response = await client.post(
    #         "/auth/send-otp/v1/messaging/send_sms", params={"phone_number": phone_number, "otp_code": otp_code}
    #     )
    #     if sms_response.status_code != 200:
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP SMS.")

    # Return the created OTP entry data in the response
    return {
        "message": "Pre-registration successful. OTP sent via email and SMS.",
        "data": {
            "full_name": otp_entry.full_name,
            "user_name": otp_entry.user_name,
            "phone_number": otp_entry.phone_number,
            "email": otp_entry.email,
            "otp_code": otp_entry.otp_code,
            "expires_at": otp_entry.expires_at,
            "is_verified": otp_entry.is_verified,
            "referral_code": otp_entry.referral_code
        }
    }

# Complete Rider Registration
@router.post("/rider-complete-registration/", status_code=status.HTTP_200_OK)
async def complete_registration(
    phone_number: str = Form(...),
    otp_code: str = Form(...),
    referral_code: Optional[str] = Form(None), 
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        # Validate OTP
        otp_query = await session.execute(
            select(OTPVerification).filter(
                OTPVerification.phone_number == phone_number,
                OTPVerification.otp_code == otp_code,
                OTPVerification.expires_at > datetime.utcnow(),
                OTPVerification.is_verified == False
            )
        )
        otp_entry = otp_query.scalar()

        if not otp_entry:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")

        # Mark OTP as verified
        otp_entry.is_verified = True
        await session.commit()

        # Generate a unique account number
        account_number = f"ACC{random.randint(10000000, 99999999)}"

        # Create User
        user = User(
            full_name=otp_entry.full_name,
            user_name=otp_entry.user_name,
            phone_number=otp_entry.phone_number,
            email=otp_entry.email,
            hashed_password=otp_entry.hashed_password,
            user_type=UserType.RIDER  # Assuming UserType Enum includes RIDER
        )
        session.add(user)
        await session.flush()  # Flush to get the user.id before creating the Rider

        # Create Rider associated with the User
        rider = Rider(
            user_id=user.id  # Associate Rider with the newly created User
        )
        session.add(rider)
        await session.flush()  # Flush to get the rider.id before creating the wallet

        # Create Wallet associated with the User
        wallet = Wallet(
            user_id=user.id,  # Use the user.id as a foreign key in the Wallet
            balance=0.0,
            account_number=account_number
        )
        session.add(wallet)

        # Handle referral code if provided
        if referral_code:
            # Check if referral code belongs to a rider
            referrer_rider_query = await session.execute(
                select(Rider).filter(Rider.referral_code == referral_code)
            )
            referrer_rider = referrer_rider_query.scalars().first()

            # Check if referral code belongs to a driver if not found in riders
            referrer_driver = None
            if not referrer_rider:
                referrer_driver_query = await session.execute(
                    select(Driver).filter(Driver.referral_code == referral_code)
                )
                referrer_driver = referrer_driver_query.scalars().first()

            # Raise an error if the referral code is invalid
            if not referrer_rider and not referrer_driver:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid referral code.")

            # Create a referral relationship based on the referrer type
            referral = Referral(
                referrer_rider_id=referrer_rider.id if referrer_rider else None,
                referrer_driver_id=referrer_driver.id if referrer_driver else None,
                referred_rider_id=rider.id  # Use the new rider's id
            )
            session.add(referral)

        await session.commit()  # Commit the User, Rider, Wallet, and Referral entries

        return {"message": "Registration completed successfully", "account_number": account_number}
    

# Rider Signup Endpoint
@router.post("/signup/rider/", status_code=status.HTTP_201_CREATED)
async def signup_rider(
    full_name: str = Form(...),
    user_name: str = Form(...),
    phone_number: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    address: Optional[str] = Form(None),
    # rider_photo: UploadFile = File(...),
    referral_code: Optional[str] = Form(None),  # Add referral code field
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        # Check if email already exists
        existing_email = await session.execute(
            select(User).filter(User.email == email)
        )
        existing_email = existing_email.scalars().first()

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email is already registered."
            )

        # Check if phone number already exists
        existing_phone = await session.execute(
            select(User).filter(User.phone_number == phone_number)
        )
        existing_phone = existing_phone.scalars().first()

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number is already registered."
            )

        # Check if username already exists
        existing_username = await session.execute(
            select(User).filter(User.user_name == user_name)
        )
        existing_username = existing_username.scalars().first()

        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this username is already registered."
            )

        # If no duplicates are found, proceed with creating the user
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
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        # Create wallet for the user
        account_number = generate_global_unique_account_number()
        db_wallet = Wallet(user_id=db_user.id, balance=0.0, account_number=account_number)
        session.add(db_wallet)
        await session.commit()
        await session.refresh(db_wallet)

        # Save rider-specific data
        # file_content = await rider_photo.read()
        db_rider = Rider(
            user_id=db_user.id,
            # rider_photo=file_content,
        )
        session.add(db_rider)
        await session.commit()
        await session.refresh(db_rider)

        # Handle referral code if provided
        if referral_code:
            referrer = await session.execute(select(Rider).filter(Rider.referral_code == referral_code))
            referrer_rider = referrer.scalars().first()

            if referrer_rider:
                referral = Referral(
                    referrer_id=referrer_rider.id,
                    referred_rider_id=db_rider.id
                )
                session.add(referral)
                await session.commit()

    return {
        "message": "Rider registration successful",
        "account_number": account_number
    }


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
    # driver_photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        # Check if license number already exists for another driver
        existing_license = await session.execute(
            select(Driver).filter(Driver.license_number == license_number)
        )
        existing_license = existing_license.scalars().first()
        if existing_license:
            raise HTTPException(status_code=400, detail="License number already exists.")

        # Check if email already exists
        existing_email = await session.execute(
            select(User).filter(User.email == email)
        )
        existing_email = existing_email.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email is already registered."
            )

        # Check if phone number already exists
        existing_phone = await session.execute(
            select(User).filter(User.phone_number == phone_number)
        )
        existing_phone = existing_phone.scalars().first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number is already registered."
            )

        # Check if username already exists
        existing_username = await session.execute(
            select(User).filter(User.user_name == user_name)
        )
        existing_username = existing_username.scalars().first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this username is already registered."
            )

        # If no user exists with the provided phone number, email, or username, proceed
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
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        # Create wallet for the user
        account_number = generate_global_unique_account_number()
        db_wallet = Wallet(user_id=db_user.id, balance=0.0, account_number=account_number)
        session.add(db_wallet)
        await session.commit()
        await session.refresh(db_wallet)

    # Save driver-specific data
    # file_content = await driver_photo.read()
    db_driver = Driver(
        user_id=db_user.id,
        license_number=license_number,
        license_expiry=license_expiry,
        years_of_experience=years_of_experience,
        # driver_photo=file_content
    )
    session.add(db_driver)
    await session.commit()
    await session.refresh(db_driver)

    return {"message": "Driver registration successful", "account_number": account_number}


# OTP Verification
@router.post("/verify-otp/")
async def verify_otp(
    phone_number: str,
    otp_code: str,
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        otp_entry = await session.execute(
            select(OTPVerification).filter(
                OTPVerification.phone_number == phone_number,
                OTPVerification.otp_code == otp_code,
                OTPVerification.expires_at > datetime.utcnow(),
                OTPVerification.is_verified == False
            )
        )
        otp_entry = otp_entry.scalars().first()

        if not otp_entry:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")

        # Mark OTP as verified
        otp_entry.is_verified = True
        await session.commit()

        # Create a new User using the details in OTPVerification
        db_user = User(
            full_name=otp_entry.full_name,
            user_name=otp_entry.user_name,
            phone_number=otp_entry.phone_number,
            email=otp_entry.email,
            hashed_password=otp_entry.hashed_password,
            user_type="RIDER"
        )
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)  # Refresh to get the new user ID

        # Create a wallet for the new user
        account_number = generate_global_unique_account_number()  # Function to generate a unique account number
        db_wallet = Wallet(
            user_id=db_user.id,
            balance=0.0,  # Initial balance
            account_number=account_number
        )
        session.add(db_wallet)
        await session.commit()

        return {
            "message": "OTP verified, user registered successfully, and wallet created.",
            "account_number": account_number
        }



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


# Rider Referal Code Endpoint
@router.get("/rider/referral-code/{rider_id}", status_code=status.HTTP_200_OK)
async def get_referral_code(rider_id: int, db: AsyncSession = Depends(get_async_db)):
    # Ensure the rider exists in the database
    result = await db.execute(select(Rider).filter(Rider.id == rider_id))
    rider = result.scalars().first()

    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Check if the rider already has a referral code
    if rider.referral_code:
        return {
            "referral_code": rider.referral_code
        }

    # Generate a new referral code
    referral_code = generate_hashed_referral_code()

    # Set the new referral code
    rider.referral_code = referral_code

    # Commit the changes to the database
    try:
        db.add(rider)  # Mark the rider instance for update
        await db.commit()  # Commit the transaction
        await db.refresh(rider)  # Refresh the rider instance
    except Exception as e:
        await db.rollback()  # Rollback in case of error
        raise HTTPException(status_code=500, detail=f"An error occurred while saving the referral code: {e}")

    return {
        "referral_code": rider.referral_code
    }


# Driver Referral
@router.get("/driver/referral-code/{driver_id}", status_code=status.HTTP_200_OK)
async def get_driver_referral_code(driver_id: int, db: AsyncSession = Depends(get_async_db)):
    # Ensure the driver exists in the database
    result = await db.execute(select(Driver).filter(Driver.id == driver_id))
    driver = result.scalars().first()

    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Check if the driver already has a referral code
    if driver.referral_code:
        return {
            "referral_code": driver.referral_code
        }

    # Generate a new referral code
    referral_code = generate_hashed_referral_code()

    # Set the new referral code
    driver.referral_code = referral_code

    # Commit the changes to the database
    try:
        db.add(driver)  # Mark the driver instance for update
        await db.commit()  # Commit the transaction
        await db.refresh(driver)  # Refresh the driver instance
    except Exception as e:
        await db.rollback()  # Rollback in case of error
        raise HTTPException(status_code=500, detail=f"An error occurred while saving the referral code: {e}")

    return {
        "referral_code": driver.referral_code
    }



# Update Rider Profile
# Helper function to save the image to disk
async def save_image(file: UploadFile, folder: str) -> str:
    file_directory = f"./assets/riders/{folder}"
    os.makedirs(file_directory, exist_ok=True)  # Create directory if it doesn’t exist
    file_path = os.path.join(file_directory, file.filename)
    
    # Save the file asynchronously
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()  # Read file contents
        await out_file.write(content)  # Write to disk
    return file_path  # Return the file path for storage in the database

@router.put("/riders/{rider_id}/profile", response_model=RiderProfileUpdate)
async def update_rider_profile(
    rider_id: int,
    gender: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    nin: Optional[str] = Form(None),
    profile_photo: Union[UploadFile, None] = File(None),
    nin_photo: Union[UploadFile, None] = File(None),
    db: AsyncSession = Depends(get_async_db)
):
    # Retrieve the rider profile
    result = await db.execute(select(Rider).where(Rider.id == rider_id))
    rider = result.scalar_one_or_none()

    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Update rider fields if provided
    if nin:
        rider.nin = nin

    # Handle profile photo upload
    if profile_photo:
        profile_photo_path = await save_image(profile_photo, "profile_photos")
        rider.rider_photo = profile_photo_path  # Save the file path in the database

    # Handle NIN photo upload
    if nin_photo:
        nin_photo_path = await save_image(nin_photo, "nin_photos")
        rider.nin_photo = nin_photo_path  # Save the file path in the database

    # Retrieve associated user and update relevant fields
    user = await db.get(User, rider.user_id)
    if user:
        if gender:
            user.gender = gender
        if address:
            user.address = address
        # Update email without validation
        if email:
            user.email = email
        if phone_number:
            user.phone_number = phone_number
    else:
        raise HTTPException(status_code=404, detail="Associated user not found")

    # Commit changes to the database
    await db.commit()
    await db.refresh(rider)

    return RiderProfileUpdate(
        rider_id=rider.id,
        gender=user.gender if user else None,
        address=user.address if user else None,
        nin=rider.nin,
        email=user.email if user else None,
        phone_number=user.phone_number if user else None,
        profile_photo=rider.rider_photo,
        nin_photo=rider.nin_photo
    )

# Get Rider Profile
@router.get("/riders/{rider_id}/profile", response_model=RiderProfile)
async def get_rider_profile(
    rider_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    # Retrieve the rider profile
    result = await db.execute(select(Rider).where(Rider.id == rider_id))
    rider = result.scalar_one_or_none()

    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Retrieve associated User information
    user_result = await db.execute(select(User).where(User.id == rider.user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found")

    # Combine selected profile details from Rider and User, returning only the profile photo path
    profile_data = {
        "rider_id": rider.id,
        "gender": user.gender,
        "address": user.address,
        "nin": rider.nin,
        "profile_photo": rider.rider_photo,  # Return the file path instead of Base64
        "email": user.email,
        "phone_number": user.phone_number,
        "full_name": user.full_name,
    }

    return profile_data
