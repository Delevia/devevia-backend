from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from ..database import get_async_db
from ..models import User, Rider, Driver, KYC, Admin, Wallet, Referral
from ..schemas import KycCreate, AdminCreate, get_password_hash
from ..utils.schemas_utils import UserProfileResponse
from ..utils.utils_dependencies_files import get_current_user, generate_hashed_referral_code
from ..utils.wallet_utilitity_functions import generate_global_unique_account_number
import logging
import os
from ..utils.otp import generate_otp, OTPVerification, generate_otp_expiration
import httpx
import random
from sqlalchemy.future import select
from fastapi import HTTPException
from ..enums import UserType
from pydantic import BaseModel, Field
from app.utils.security import hash_password


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


    # Send OTP via email
    # async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
    #     email_response = await client.post(
    #         "/auth/send-otp-email", params={"to_email": email, "otp_code": otp_code}  # Send as query params
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

    return {"message": "Pre-registration successful. OTP sent via email and SMS."}


@router.post("/rider-complete-registration/", status_code=status.HTTP_200_OK)
async def complete_registration(
    phone_number: str = Form(...),
    otp_code: str = Form(...),
    referral_code: Optional[str] = Form(None),  # Optional referral code
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
            referrer = await session.execute(select(Rider).filter(Rider.referral_code == referral_code))
            referrer_rider = referrer.scalars().first()

            if referrer_rider:
                # Create a referral relationship
                referral = Referral(
                    referrer_id=referrer_rider.id,
                    referred_rider_id=rider.id  # Use the new rider's id
                )
                session.add(referral)

        await session.commit()  # Commit the User, Rider, and Wallet entries

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


# Referal Code Endpoint
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
