from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_db  # Ensure to update this to get the async session
from ..schemas import LoginSchema
from ..models import User, RefreshToken, BlacklistedToken
from ..schemas import RefreshTokenRequest, RequestTokenResponse, LogoutRequest
from ..schemas import pwd_context
from dotenv import load_dotenv
import os
import requests
from ..utils.otp import generate_otp, OTPVerification, generate_otp_expiration
from ..utils.schemas_utils import OtpPhoneNumberRequest
from ..utils.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    decode_refresh_token
)

load_dotenv()

# Get environment variables
SMART_SMS_API_URL = os.getenv("SMART_SMS_API_URL")
API_KEY = os.getenv("API_KEY")
SENDER_ID = os.getenv("SENDER_ID")

router = APIRouter()

# Reusable function to verify password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Rider Login Endpoint
@router.post("/login/rider/", status_code=status.HTTP_200_OK)
async def login_rider(
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        rider = await session.execute(
            User.select().filter(User.phone_number == login_data.phone_number, User.user_type == "RIDER")
        )
        rider = rider.scalar()

        if not rider or not verify_password(login_data.password, rider.hashed_password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")

        access_token = create_access_token(data={"sub": str(rider.id)})
        refresh_token = await create_refresh_token(data={"sub": str(rider.id)}, db=session)

        return {
            "message": "Login Successful",
            "user_id": rider.id,
            "user_type": rider.user_type,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

# Driver Login Endpoint
@router.post("/login/driver/", status_code=status.HTTP_200_OK)
async def login_driver(
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        driver = await session.execute(
            User.select().filter(User.phone_number == login_data.phone_number, User.user_type == "DRIVER")
        )
        driver = driver.scalar()

        if not driver or not verify_password(login_data.password, driver.hashed_password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")

        access_token = create_access_token(data={"sub": str(driver.id)})
        refresh_token = await create_refresh_token(data={"sub": str(driver.id)}, db=session)

        return {
            "message": "Login Successful",
            "user_id": driver.id,
            "user_type": driver.user_type,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

# Refresh Token Endpoint to get new Access Token
@router.post("/refresh", response_model=RequestTokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_async_db)):
    async with db as session:
        # Check if the refresh token is blacklisted
        blacklisted_token = await session.execute(
            BlacklistedToken.select().filter(BlacklistedToken.token == request.refresh_token)
        )
        blacklisted_token = blacklisted_token.scalar()

        if blacklisted_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # Decode the refresh token
        user_data = await decode_refresh_token(request.refresh_token, session)

        if not user_data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # Generate a new access token
        access_token = create_access_token(data={"sub": str(user_data["sub"])})

        return {"access_token": access_token, "token_type": "bearer"}

# Send OTP For User Registration
@router.post("/send-otp/")
async def send_otp(request: OtpPhoneNumberRequest, db: AsyncSession = Depends(get_async_db)):
    phone_number = request.phone_number

    async with db as session:
        # Check if the phone number already exists in the Users table
        existing_user = await session.execute(
            User.select().filter(User.phone_number == phone_number)
        )
        existing_user = existing_user.scalar()

        if existing_user:
            raise HTTPException(status_code=400, detail="Phone Number already exists")

        # Generate OTP and expiration time
        otp_code = generate_otp()
        expiration_time = generate_otp_expiration()

        # Check if an OTP already exists for the phone number
        existing_otp = await session.execute(
            OTPVerification.select().filter(OTPVerification.phone_number == phone_number)
        )
        existing_otp = existing_otp.scalar()

        if existing_otp:
            # Update the existing OTP record
            existing_otp.otp_code = otp_code
            existing_otp.expires_at = expiration_time
            existing_otp.is_verified = False
            await session.commit()
            await session.refresh(existing_otp)
        else:
            # If no existing OTP, create a new one
            otp_entry = OTPVerification(
                phone_number=phone_number,
                otp_code=otp_code,
                expires_at=expiration_time
            )
            session.add(otp_entry)
            await session.commit()
            await session.refresh(otp_entry)

        # Send the OTP via SmartSMS
        payload = {
            'token': API_KEY,
            'sender': SENDER_ID,
            'to': phone_number,
            'message': f"Your Delevia OTP is {otp_code}. It expires in 5 minutes.",
            'type': '0',
            'routing': '3',
            'ref_id': 'unique-ref-id',
        }

        response = requests.post(SMART_SMS_API_URL, data=payload)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to send OTP")

        return {"message": "OTP sent successfully"}

# Logout Endpoint
@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: LogoutRequest, db: AsyncSession = Depends(get_async_db)):
    refresh_token = request.refresh_token

    async with db as session:
        # Find the refresh token
        token_record = await session.execute(
            RefreshToken.select().filter(RefreshToken.token == refresh_token)
        )
        token_record = token_record.scalar()

        if not token_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refresh token not found")

        # Mark the refresh token as revoked
        token_record.is_revoked = True
        await session.commit()

        # Blacklist the refresh token
        blacklisted_refresh_token = BlacklistedToken(token=refresh_token)
        session.add(blacklisted_refresh_token)

        # Optionally, blacklist the access token if provided
        if request.access_token:
            blacklisted_access_token = BlacklistedToken(token=request.access_token)
            session.add(blacklisted_access_token)

        # Commit all changes
        await session.commit()

    return {"message": "Logout successful"}
