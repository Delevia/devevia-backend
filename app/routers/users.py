from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from datetime import date
from ..database import get_async_db
from ..models import User, Rider, Driver, KYC, Admin, Wallet, Referral
from ..schemas import KycCreate, AdminCreate, get_password_hash
from ..utils.schemas_utils import UserProfileResponse
from ..utils.utils_dependencies_files import get_current_user, generate_hashed_referral_code
from ..utils.wallet_utilitity_functions import generate_account_number
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
        account_number = generate_account_number()
        db_wallet = Wallet(user_id=db_user.id, balance=0.0, account_number=account_number)
        session.add(db_wallet)
        await session.commit()
        await session.refresh(db_wallet)

        # Save rider-specific data
        file_content = await rider_photo.read()
        db_rider = Rider(
            user_id=db_user.id,
            rider_photo=file_content,
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
    driver_photo: UploadFile = File(...),
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
        account_number = generate_account_number()
        db_wallet = Wallet(user_id=db_user.id, balance=0.0, account_number=account_number)
        session.add(db_wallet)
        await session.commit()
        await session.refresh(db_wallet)

    # Save driver-specific data
    file_content = await driver_photo.read()
    db_driver = Driver(
        user_id=db_user.id,
        license_number=license_number,
        license_expiry=license_expiry,
        years_of_experience=years_of_experience,
        driver_photo=file_content
    )
    session.add(db_driver)
    await session.commit()
    await session.refresh(db_driver)

    return {"message": "Driver registration successful", "account_number": account_number}


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