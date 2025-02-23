from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
from typing import Any, Optional, Union
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from datetime import datetime, date, timezone  
from ..database import get_async_db
from ..models import User, Rider, Driver, KYC, Admin, Wallet, Referral, PasswordReset, TemporaryUserPhoto, PanicButton
from ..schemas import KycCreate, AdminCreate, get_password_hash, pwd_context
from ..utils.schemas_utils import RiderProfileUpdate, RiderProfile, PreRegisterRequest, DriverPreRegisterRequest, RiderProfileUpdateus, RiderProfileus
from ..utils.utils_dependencies_files import get_current_user, generate_hashed_referral_code
from ..utils.wallet_utilitity_functions import generate_global_unique_account_number
import logging
import os
import uuid
from ..utils.otp import generate_otp, OTPVerification, generate_otp_expiration
from uuid import uuid4
import random
from sqlalchemy.future import select
from fastapi import HTTPException
from ..enums import UserType
from pydantic import BaseModel, Field, EmailStr, ValidationError
from app.utils.security import hash_password
import aiofiles
from sqlalchemy.orm import joinedload
import httpx
from fastapi import HTTPException, Query

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



@router.post("/pre-register/rider/new/", status_code=status.HTTP_200_OK)
async def pre_register_rider(
    request: PreRegisterRequest,
    country: str,  # Add country as a parameter
    db: AsyncSession = Depends(get_async_db)
):
    # Extract data from the request
    full_name = request.full_name
    user_name = request.user_name
    phone_number = request.phone_number
    email = request.email
    password = request.password
    referral_code = request.referral_code

    # Validate country parameter
    if country not in ["Nigeria", "USA"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid country. Please specify 'Nigeria' or 'USA'."
        )

    async with db as session:
        # Check if phone number, email, or username is already registered in the User table
        user_query = await session.execute(
            select(User).filter(
                (User.phone_number == phone_number) |
                (User.email == email) |
                (User.user_name == user_name)
            )
        )
        existing_user = user_query.scalars().first()

        if existing_user:
            # If any of the values exist, raise an exception with relevant message
            if existing_user.phone_number == phone_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number is already associated with another user."
                )
            elif existing_user.email == email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address is already associated with another user."
                )
            elif existing_user.user_name == user_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username is already taken by another user."
                )

        # Check if the credentials already exist in the OTPVerification table
        otp_query = await session.execute(
            select(OTPVerification).filter(
                (OTPVerification.phone_number == phone_number) |
                (OTPVerification.email == email) |
                (OTPVerification.user_name == user_name)
            )
        )
        existing_otp = otp_query.scalars().first()

        if existing_otp:
            # If OTP is already sent for the credentials, raise an exception
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has already been sent to your email. Please check your inbox."
            )

        # Handle referral code validation
        referrer_rider = None
        referrer_driver = None
        if referral_code:
            referrer_rider_query = await session.execute(
                select(Rider).filter(Rider.referral_code == referral_code)
            )
            referrer_rider = referrer_rider_query.scalars().first()

            if not referrer_rider:
                referrer_driver_query = await session.execute(
                    select(Driver).filter(Driver.referral_code == referral_code)
                )
                referrer_driver = referrer_driver_query.scalars().first()

            if not referrer_rider and not referrer_driver:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid referral code."
                )

        # Generate OTP and expiration time
        otp_code = generate_otp()
        expiration_time = generate_otp_expiration()

        # Send OTP via email
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            email_response = await client.post(
                "/auth/send-otp-email",
                params={"to_email": email, "otp_code": otp_code}
            )
            if email_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP email."
                )

        # Handle country-specific fields and save OTP data
        otp_entry = OTPVerification(
            full_name=full_name,
            user_name=user_name,
            phone_number=phone_number,
            email=email,
            otp_code=otp_code,
            expires_at=expiration_time,
            is_verified=False,
            hashed_password=hash_password(password),
            referral_code=referral_code
        )
        session.add(otp_entry)
        await session.commit()
        await session.refresh(otp_entry)

    return {
        "message": "Pre-registration successful. OTP sent via email.",
        "data": {
            "full_name": otp_entry.full_name,
            "user_name": otp_entry.user_name,
            "phone_number": otp_entry.phone_number,
            "email": otp_entry.email,
            "otp_code": otp_entry.otp_code,
            "expires_at": otp_entry.expires_at,
            "is_verified": otp_entry.is_verified,
            "referral_code": otp_entry.referral_code,
        }
    }


# Helper function to save the image to disk
async def save_image(file: UploadFile, folder: str) -> str:
    # Ensure the folder path is available
    file_directory = f"./assets/riders/{folder}"
    os.makedirs(file_directory, exist_ok=True)  # Create directory if it doesn’t exist
    
    # Generate a unique filename to prevent overwriting
    unique_filename = f"{uuid4().hex}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = os.path.join(file_directory, unique_filename)
    
    try:
        # Save the file asynchronously
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()  # Read file contents
            await out_file.write(content)  # Write to disk
    except Exception as e:
        # Handle any potential errors that occur during file save
        print(f"Error saving file {file.filename}: {e}")
        raise e

    return file_path  # Return the file path for storage in the database


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
        account_number = f"{random.randint(1000000000, 9999999999)}"

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

        # Construct the user data to return
        user_data = {
            "id": user.id,
            "full_name": user.full_name,
            "user_name": user.user_name,
            "phone_number": user.phone_number,
            "email": user.email,
            "user_type": user.user_type,
            "account_number": account_number
        }

        return {
            "message": "Registration completed successfully", 
            "user": user_data
        }


@router.post("/pre-register/driver/", status_code=status.HTTP_200_OK)
async def pre_register_driver(
    request: DriverPreRegisterRequest,
    db: AsyncSession = Depends(get_async_db)
):
    # Extract data from the request
    full_name = request.full_name
    user_name = request.user_name
    phone_number = request.phone_number
    email = request.email
    password = request.password

    async with db as session:
        # Check if phone number, email, or username is already registered by any user (driver or rider)
        existing_user_query = await session.execute(
            select(User)
            .filter(
                (User.phone_number == phone_number) |
                (User.email == email) |
                (User.user_name == user_name)
            )
        )
        existing_user = existing_user_query.scalars().first()

        if existing_user:
            if existing_user.phone_number == phone_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number is already associated with another user."
                )
            elif existing_user.email == email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address is already associated with another user."
                )
            elif existing_user.user_name == user_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username is already taken by another user."
                )

        # Check if the credentials already exist in the OTPVerification table
        otp_query = await session.execute(
            select(OTPVerification).filter(
                (OTPVerification.phone_number == phone_number) |
                (OTPVerification.email == email) |
                (OTPVerification.user_name == user_name)
            )
        )
        existing_otp = otp_query.scalars().first()

        if existing_otp:
            # If OTP is already sent for the credentials, raise an exception
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has already been sent to your email. Please check your inbox."
            )

        # Generate OTP and expiration time
        otp_code = generate_otp()
        expiration_time = generate_otp_expiration()

        # Store the user data along with the OTP in the OTPVerification table
        otp_entry = OTPVerification(
            full_name=full_name,
            user_name=user_name,
            phone_number=phone_number,
            email=email,
            otp_code=otp_code,
            expires_at=expiration_time,
            is_verified=False,
            hashed_password=hash_password(password),  # Hash the password for storage
        )
        session.add(otp_entry)
        await session.commit()
        await session.refresh(otp_entry)

    # Send OTP via email
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        email_response = await client.post(
            "/auth/send-otp-email",
            params={"to_email": email, "otp_code": otp_code}
        )
        if email_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP email."
            )
    
    # Optionally, send OTP via SMS (if you want to include this functionality)
    # async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
    #     sms_response = await client.post(
    #         "/auth/send-otp/v1/messaging/send_sms", params={"phone_number": phone_number, "otp_code": otp_code}
    #     )
    #     if sms_response.status_code != 200:
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP SMS.")

    # Return the created OTP entry data in the response
    return {
        "message": "Pre-registration successful. OTP sent via email.",
        "data": {
            "full_name": otp_entry.full_name,
            "user_name": otp_entry.user_name,
            "phone_number": otp_entry.phone_number,
            "email": otp_entry.email,
            "otp_code": otp_entry.otp_code,
            "expires_at": otp_entry.expires_at,
            "is_verified": otp_entry.is_verified,
        }
    }


# Verify OTP For Driver
@router.post("/verify-otp/driver", status_code=status.HTTP_200_OK)
async def verify_driver_otp(
    phone_number: str = Form(...),
    otp_code: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        otp_query = await session.execute(
            select(OTPVerification).where(
                OTPVerification.phone_number == phone_number,
                OTPVerification.otp_code == otp_code,
                OTPVerification.expires_at > datetime.utcnow(),
                OTPVerification.is_verified == False
            )
        )
        otp_entry = otp_query.scalar()

        if not otp_entry:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")

        otp_entry.is_verified = True
        await session.commit()
    
    return {"message": "OTP verified. Please proceed to complete the registration."}


# Helper function to save an image and return its file path
async def save_image(file: UploadFile, folder: str) -> str:
    os.makedirs(folder, exist_ok=True)  # Ensure the directory exists

    # Generate a unique filename
    filename = f"{uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = os.path.join(folder, filename)

    # Save the file
    with open(file_path, "wb") as image_file:
        content = await file.read()  # Read the file contents
        image_file.write(content)   # Write the contents to the file
    
    return file_path


# Use Transactions for Atomicity  When you wrap the entire registration process in a transaction,
#  any failure (e.g., network error) will automatically roll back all changes made to the database 
# within that transaction, ensuring data consistency.

@router.post("/complete-registration/driver", status_code=status.HTTP_201_CREATED)
async def complete_driver_registration(
    phone_number: str = Form(...),
    license_number: str = Form(...),
    license_expiry: date = Form(...),
    years_of_experience: int = Form(...),
    vehicle_name: str = Form(...),
    vehicle_model: str = Form(...),
    vehicle_exterior_color: str = Form(...),
    vehicle_interior_color: str = Form(...),
    nin_number: str = Form(...),
    vehicle_insurance_policy: UploadFile = File(...),  # Updated
    driver_photo: UploadFile = File(...),
    nin_photo: UploadFile = File(...),
    proof_of_ownership: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    async with db.begin():
        otp_query = await db.execute(
            select(OTPVerification).where(
                OTPVerification.phone_number == phone_number,
                OTPVerification.is_verified == True
            )
        )
        otp_entry = otp_query.scalar()
        if not otp_entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pre-registration not found or OTP not verified."
            )

        user_query = await db.execute(
            select(User).where(User.phone_number == otp_entry.phone_number)
        )
        if user_query.scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists."
            )

        if await db.scalar(select(Driver).where(Driver.nin_number == nin_number)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver with this NIN already exists."
            )
        if await db.scalar(select(Driver).where(Driver.license_number == license_number)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver with this license number already exists."
            )

        user = User(
            full_name=otp_entry.full_name,
            user_name=otp_entry.user_name,
            phone_number=otp_entry.phone_number,
            email=otp_entry.email,
            hashed_password=otp_entry.hashed_password,
            user_type=UserType.DRIVER,
            user_status="AWAITING",
            created_at=datetime.utcnow()
        )
        db.add(user)
        await db.flush()

        # Save the images and the vehicle insurance policy
        driver_photo_path = await save_image(driver_photo, './assets/drivers/driver_photos')
        nin_photo_path = await save_image(nin_photo, './assets/drivers/nin_photos')
        proof_of_ownership_path = await save_image(proof_of_ownership, './assets/drivers/proof_of_ownership')
        vehicle_insurance_policy_path = await save_image(vehicle_insurance_policy, './assets/drivers/insurance_policies')  # Added

        driver = Driver(
            user_id=user.id,
            driver_photo=driver_photo_path,
            license_number=license_number,
            license_expiry=license_expiry,
            years_of_experience=years_of_experience,
            vehicle_name=vehicle_name,
            vehicle_model=vehicle_model,
            vehicle_insurance_policy=vehicle_insurance_policy_path,  # Updated
            vehicle_exterior_color=vehicle_exterior_color,
            vehicle_interior_color=vehicle_interior_color,
            nin_photo=nin_photo_path,
            nin_number=nin_number,
            proof_of_ownership=proof_of_ownership_path,
            rating=100  # Default rating for all new drivers
        )
        db.add(driver)

        wallet = Wallet(
            user_id=user.id,
            balance=0.0,
            account_number=f"{random.randint(1000000000, 9999999999)}"
        )
        db.add(wallet)

    await db.refresh(user)
    await db.refresh(driver)
    await db.refresh(wallet)

    return {
        "message": "Driver registration and account creation completed successfully.",
        "data": {
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "user_name": user.user_name,
                "phone_number": user.phone_number,
                "email": user.email,
                "user_type": user.user_type,
                "user_status": user.user_status,
                "created_at": user.created_at,
            },
            "driver": {
                "driver_id": driver.id,
                "driver_photo": driver.driver_photo,
                "license_number": driver.license_number,
                "license_expiry": driver.license_expiry,
                "years_of_experience": driver.years_of_experience,
                "vehicle_name": driver.vehicle_name,
                "vehicle_model": driver.vehicle_model,
                "vehicle_insurance_policy": driver.vehicle_insurance_policy,  # Updated
                "vehicle_exterior_color": driver.vehicle_exterior_color,
                "vehicle_interior_color": driver.vehicle_interior_color,
                "nin_photo": driver.nin_photo,
                "nin_number": driver.nin_number,
                "proof_of_ownership": driver.proof_of_ownership,
                "rating": driver.rating  # Include the rating in the response
            },
            "wallet": {
                "balance": wallet.balance,
                "account_number": wallet.account_number,
            }
        }
    }

@router.post("/complete-registration/driver/usa", status_code=status.HTTP_201_CREATED)
async def complete_driver_registration(
    phone_number: str = Form(...),
    license_number: str = Form(...),
    license_expiry: date = Form(...),
    years_of_experience: int = Form(...),
    vehicle_name: str = Form(...),
    vehicle_model: str = Form(...),
    vehicle_exterior_color: str = Form(...),
    vehicle_interior_color: str = Form(...),
    ssn_number: str = Form(...),
    vehicle_inspection_approval: UploadFile = File(...),
    vehicle_insurance_policy: UploadFile = File(...),
    driver_photo: UploadFile = File(...),
    proof_of_ownership: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    async with db.begin():
        otp_query = await db.execute(
            select(OTPVerification).where(
                OTPVerification.phone_number == phone_number,
                OTPVerification.is_verified == True
            )
        )
        otp_entry = otp_query.scalar()
        if not otp_entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pre-registration not found or OTP not verified."
            )

        user_query = await db.execute(
            select(User).where(User.phone_number == otp_entry.phone_number)
        )
        if user_query.scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists."
            )

        if await db.scalar(select(Driver).where(Driver.nin_number == ssn_number)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver with this NIN already exists."
            )
        if await db.scalar(select(Driver).where(Driver.license_number == license_number)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver with this license number already exists."
            )

        user = User(
            full_name=otp_entry.full_name,
            user_name=otp_entry.user_name,
            phone_number=otp_entry.phone_number,
            email=otp_entry.email,
            hashed_password=otp_entry.hashed_password,
            user_type=UserType.DRIVER,
            user_status="AWAITING",
            created_at=datetime.utcnow()
        )
        db.add(user)
        await db.flush()

        driver_photo_path = await save_image(driver_photo, './assets/drivers/driver_photos')
        proof_of_ownership_path = await save_image(proof_of_ownership, './assets/drivers/proof_of_ownership')
        vehicle_inspection_approval_path = await save_image(
            vehicle_inspection_approval, './assets/drivers/vehicle_inspection_approvals'
        )
        vehicle_insurance_policy_path = await save_image(vehicle_insurance_policy, './assets/drivers/vehicle_insurance_policies')

        driver = Driver(
            user_id=user.id,
            driver_photo=driver_photo_path,
            license_number=license_number,
            license_expiry=license_expiry,
            years_of_experience=years_of_experience,
            vehicle_name=vehicle_name,
            vehicle_model=vehicle_model,
            vehicle_insurance_policy=vehicle_insurance_policy_path,
            vehicle_exterior_color=vehicle_exterior_color,
            vehicle_interior_color=vehicle_interior_color,
            ssn_number=ssn_number,
            proof_of_ownership=proof_of_ownership_path,
            vehicle_inspection_approval=vehicle_inspection_approval_path,
            rating=100  # Set initial rating to 100
        )
        db.add(driver)

        wallet = Wallet(
            user_id=user.id,
            balance=0.0,
            account_number=f"{random.randint(1000000000, 9999999999)}"
        )
        db.add(wallet)

    await db.refresh(user)
    await db.refresh(driver)
    await db.refresh(wallet)

    return {
        "message": "Driver registration and account creation completed successfully.",
        "data": {
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "user_name": user.user_name,
                "phone_number": user.phone_number,
                "email": user.email,
                "user_type": user.user_type,
                "user_status": user.user_status,
                "created_at": user.created_at,
            },
            "driver": {
                "driver_id": driver.id,
                "driver_photo": driver.driver_photo,
                "license_number": driver.license_number,
                "license_expiry": driver.license_expiry,
                "years_of_experience": driver.years_of_experience,
                "vehicle_name": driver.vehicle_name,
                "vehicle_model": driver.vehicle_model,
                "vehicle_insurance_policy": driver.vehicle_insurance_policy,
                "vehicle_exterior_color": driver.vehicle_exterior_color,
                "vehicle_interior_color": driver.vehicle_interior_color,
                "ssn_number": driver.ssn_number,
                "proof_of_ownership": driver.proof_of_ownership,
                "rating": driver.rating  # Include the rating in the response
            },
            "wallet": {
                "balance": wallet.balance,
                "account_number": wallet.account_number,
            }
        }
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
    # Ensure the folder path is available
    file_directory = f"./assets/riders/{folder}"
    os.makedirs(file_directory, exist_ok=True)  # Create directory if it doesn’t exist
    
    # Generate a unique filename to prevent overwriting
    unique_filename = f"{uuid4().hex}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = os.path.join(file_directory, unique_filename)
    
    try:
        # Save the file asynchronously
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()  # Read file contents
            await out_file.write(content)  # Write to disk
    except Exception as e:
        # Handle any potential errors that occur during file save
        print(f"Error saving file {file.filename}: {e}")
        raise e

    return file_path  # Return the file path for storage in the database



# Update Nigeria Profile
@router.put("/riders/{rider_id}/profile/ng", response_model=RiderProfileUpdate)
async def update_rider_profile_ng(
    rider_id: int,
    gender: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    nin: str = Form(..., description="National Identification Number (NIN) is required for Nigerian riders"),
    profile_photo: Union[UploadFile, None] = File(None),
    nin_photo: UploadFile = File(..., description="NIN photo is required"),
    db: AsyncSession = Depends(get_async_db)
):
    # Retrieve the rider
    result = await db.execute(select(Rider).where(Rider.id == rider_id))
    rider = result.scalar_one_or_none()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Update NIN and NIN Photo
    rider.nin = nin
    nin_photo_path = await save_image(nin_photo, "nin_photos")
    rider.nin_photo = nin_photo_path  # Save path in the database

    # Handle profile photo upload
    if profile_photo:
        profile_photo_path = await save_image(profile_photo, "profile_photos")
        rider.rider_photo = profile_photo_path  # Save file path

    # Retrieve and update associated user
    user = await db.get(User, rider.user_id)
    if user:
        if gender:
            user.gender = gender
        if address:
            user.address = address
    else:
        raise HTTPException(status_code=404, detail="Associated user not found")

    # Commit changes
    await db.commit()
    await db.refresh(rider)

    return RiderProfileUpdate(
        rider_id=rider.id,
        gender=user.gender,
        address=user.address,
        nin=rider.nin,
        nin_photo=rider.nin_photo,
        profile_photo=rider.rider_photo
    )

# Us Profile update
@router.put("/riders/{rider_id}/profile/us", response_model=RiderProfileUpdateus)
async def update_rider_profile_us(
    rider_id: int,
    gender: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    ssn: str = Form(..., description="SSN is required for US riders"),
    profile_photo: Union[UploadFile, None] = File(None),
    db: AsyncSession = Depends(get_async_db)
):
    # Retrieve the rider
    result = await db.execute(select(Rider).where(Rider.id == rider_id))
    rider = result.scalar_one_or_none()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Update SSN
    rider.ssn_number = ssn  # Save SSN in database

    # Handle profile photo upload
    if profile_photo:
        profile_photo_path = await save_image(profile_photo, "profile_photos")
        rider.rider_photo = profile_photo_path  # Save file path

    # Retrieve and update associated user
    user = await db.get(User, rider.user_id)
    if user:
        if gender:
            user.gender = gender
        if address:
            user.address = address
    else:
        raise HTTPException(status_code=404, detail="Associated user not found")

    # Commit changes
    await db.commit()
    await db.refresh(rider)

    return RiderProfileUpdateus(
        rider_id=rider.id,
        gender=user.gender,
        address=user.address,
        ssn=rider.ssn_number,
        profile_photo=rider.rider_photo
    )



# Get Rider Profile
@router.get("/riders/{rider_id}/profile/ng", response_model=RiderProfile)
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


# Get Rider Profile Us
@router.get("/riders/{rider_id}/profile/us", response_model=RiderProfileus)
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
        "ssn": rider.ssn_number,
        "profile_photo": rider.rider_photo,  # Return the file path instead of Base64
        "email": user.email,
        "phone_number": user.phone_number,
        "full_name": user.full_name,
    }

    return profile_data


@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    email: str = Form(...),  # Form data for email
    db: AsyncSession = Depends(get_async_db)
):
    # Check if the user exists
    async with db as session:
        user_query = await session.execute(select(User).where(User.email == email))
        user = user_query.scalar()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        # Generate OTP and expiration time
        otp_code = generate_otp()
        expiration_time = generate_otp_expiration()

        # Create a new password reset record
        password_reset = PasswordReset(
            user_id=user.id,
            otp_code=otp_code,
            expires_at=expiration_time,
            used=False
        )
        session.add(password_reset)
        await session.commit()

        # Send OTP via email as query parameters
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            params = {
                "to_email": email,
                "otp_code": otp_code
            }
            email_response = await client.post(
                "/auth/send-otp-email",
                params=params  # Use params instead of data
            )
            if email_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP email."
                )

    return {"message": "Password reset OTP sent. Please check your email."}


@router.post("/users/password-reset/reset", status_code=status.HTTP_200_OK)
async def reset_password(
    otp_code: str = Form(...),
    new_password: str = Form(...),
    email: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        now = datetime.utcnow()
        print(f"Current UTC time: {now}")

        # Query for the password reset record
        query = (
            select(PasswordReset)
            .join(User, User.id == PasswordReset.user_id)
            .where(
                User.email == email,
                PasswordReset.otp_code == otp_code,
                PasswordReset.expires_at > now,  # Ensure OTP is not expired
                PasswordReset.used == False  # Ensure OTP has not been used
            )
        )

        result = await session.execute(query)
        password_reset = result.scalar()

        if not password_reset:
            print("Password reset record query returned no results.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP."
            )

        # Debugging information
        print(f"Password reset record found for email: {email}")
        print(f"Requested OTP code: {otp_code}")
        print(f"Database OTP code: {password_reset.otp_code}")
        print(f"Expires at: {password_reset.expires_at} (UTC)")
        print(f"Used status: {password_reset.used}")

        # Mark OTP as used
        password_reset.used = True
        session.add(password_reset)

        # Query for the user associated with the email
        user_query = await session.execute(select(User).where(User.email == email))
        user = user_query.scalar()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        # Hash the new password and update the user's password
        hashed_password = pwd_context.hash(new_password)
        user.hashed_password = hashed_password
        session.add(user)

        # Commit the changes to the database
        await session.commit()

    return {"message": "Password reset successfully."}



# Function to save image and return the file path
async def save_image(file: UploadFile, folder_path: str) -> str:
    # Convert folder_path to Path object
    folder = Path(folder_path)
    
    # Create the folder if it doesn't exist
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
    
    # Create a unique filename for the uploaded image
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{timestamp}_{file.filename}"
    
    # Define the full path to save the image
    file_path = folder / file_name
    
    # Save the file
    with open(file_path, "wb") as buffer:
        content = await file.read()  # Read the content of the file
        buffer.write(content)  # Write the content to the file
    
    # Return the path where the file was saved
    return str(file_path)


@router.post("/users/temp-photo/")
async def upload_temp_driver_photo(
    driver_id: int = None,
    rider_id: int = None,  # Optional for cases when it’s a driver photo
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_async_db)
):
    # Validate that the file is an image
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    try:
        # Determine if the uploaded photo is for a driver or a rider
        if driver_id:
            folder_path = './assets/temporal_photos/driver_photos'
        elif rider_id:
            folder_path = './assets/temporal_photos/riders/rider_photos'
        else:
            raise HTTPException(status_code=400, detail="Either driver_id or rider_id must be provided.")
        
        # Save the image
        photo_path = await save_image(file, folder_path)
        
        # Create a temporary record
        temp_photo = TemporaryUserPhoto(
            driver_id=driver_id,
            rider_id=rider_id,
            photo_path=photo_path
        )
        
        db.add(temp_photo)
        await db.flush()  # Ensure data is sent to the DB
        await db.commit()  # Commit the transaction

        return {"message": "Temporary photo uploaded successfully.", "photo_path": photo_path}
    
    except Exception as e:
        await db.rollback()  # Rollback the transaction in case of error
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    

