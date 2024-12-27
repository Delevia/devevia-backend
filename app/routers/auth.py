from fastapi import APIRouter, HTTPException, status, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_db  # Ensure to update this to get the async session
from ..schemas import LoginSchema
from ..models import User, RefreshToken, BlacklistedToken, PasswordReset
from ..schemas import RefreshTokenRequest, RequestTokenResponse, LogoutRequest
from ..schemas import pwd_context
from dotenv import load_dotenv
from datetime import datetime
import os
import requests
from ..utils.sendchampservices import Sendchamp
from sqlalchemy.future import select
from ..utils.otp import generate_otp, OTPVerification, generate_otp_expiration
from ..utils.schemas_utils import OtpSMSRequest
from ..utils.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    decode_refresh_token
)
from sqlalchemy.orm import joinedload
from ..utils.sendchamp_http_client import CUSTOM_HTTP_CLIENT
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from typing import Optional
from app.database import get_async_db   # Replace 'app.database' with the correct path
from fastapi.encoders import jsonable_encoder
import logging




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


load_dotenv()


# Configure SendGrid API key
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_EMAIL_SENDER = "Delevia@delevia.com"  # Use your verified SendGrid sender email

# Configue Sendchamp
SENDCHAMP_API_URL = os.getenv("SENDCHAMP_API_URL")
SENDCHAMP_PUBLIC_KEY = os.getenv("SENDCHAMP_PUBLIC_KEY")

router = APIRouter()

# Reusable function to verify password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# Rider Login Endpoint
# Rider Login Endpoint
@router.post("/login/rider/", status_code=status.HTTP_200_OK)
async def login_rider(
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        result = await session.execute(
            select(User)
            .options(joinedload(User.rider))  # Load the Rider relationship
            .filter(User.phone_number == login_data.phone_number)
        )
        user = result.scalar()

    # Check if the user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Invalid phone number or password"
        )
    
    # Ensure the user type is Rider
    if user.user_type != "RIDER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid phone number or password"
        )

    # Validate password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid phone number or password"
        )

    # Get the Rider
    rider = user.rider
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Rider not found"
        )

    # Generate tokens
    access_token = create_access_token(data={"sub": str(rider.id)})
    refresh_token = await create_refresh_token(data={"sub": str(user.id)}, db=db)  # Use user.id for refresh token

    # Prepare user data
    user_data = jsonable_encoder(user)
    user_data.pop("hashed_password", None)

    return {
        "message": "Login Successful",
        "user_type": user.user_type,
        "rider_id": rider.id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_data": user_data
    }

# Driver Login Endpoint
@router.post("/login/driver/", status_code=status.HTTP_200_OK)
async def login_driver(
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        # Retrieve user
        result = await session.execute(
            select(User)
            .options(joinedload(User.driver))  # Ensure driver is loaded
            .filter(User.phone_number == login_data.phone_number)
        )
        user = result.scalar()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid phone number or password"
            )

        if user.user_type != "DRIVER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid phone number or password"
            )

        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid phone number or password"
            )

        driver = user.driver
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )

        # Create tokens using the user ID
        access_token = create_access_token(data={"sub": str(driver.id)})
        refresh_token = await create_refresh_token(data={"sub": str(user.id)}, db=db)  # Use user.id for refresh token

        # Prepare user data
        user_data = jsonable_encoder(user)
        user_data.pop("hashed_password", None)

        return {
            "message": "Login Successful",
            "user_type": user.user_type,
            "driver_id": driver.id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_data": user_data,
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


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: LogoutRequest, db: AsyncSession = Depends(get_async_db)):
    refresh_token = request.refresh_token

    async with db as session:
        # Find the refresh token
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token)
        result = await session.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Refresh token not found"
            )

        # Check if the token is expired
        if token_record.expires_at and token_record.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token has expired"
            )

        # Check if the token is already revoked
        if token_record.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token is already revoked"
            )

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


# SendGrid Email OTp
@router.post("/send-otp-email")
async def send_otp_email(to_email: str, otp_code: str):
    if not SENDGRID_API_KEY:
        raise HTTPException(status_code=500, detail="SendGrid API key not configured")

    # Create the OTP email content
    subject = "Your OTP Code for Verification"
    html_content = f"""
    <html>
        <body>
            <h3>Your OTP Code</h3>
            <p>Your Delevia OTP code is <strong>{otp_code}</strong>. It expires in 5 minutes.</p>
        </body>
    </html>
    """

    # Create the email message
    message = Mail(
        from_email=SENDGRID_EMAIL_SENDER,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        if response.status_code not in (200, 202):
            raise HTTPException(status_code=400, detail="Failed to send OTP email")

    except Exception as e:
        print("SendGrid Error:", str(e))
        raise HTTPException(status_code=500, detail="An error occurred while sending the OTP email")

    return {"message": "OTP sent successfully via email"}



# SEndchamp OTP Sms
@router.post("/send-otp/v1/messaging/send_sms")
async def send_otp_sms(phone_number: str, otp_code: str):
    sms_data = {
        "to": [phone_number],
        "message": f"Your Delevia OTP code is {otp_code}. It expires in 5 minutes.",
        "sender_name": "Sendchamp",
        "route": "dnd"
    }

    headers = {
        "Authorization": f"Bearer {SENDCHAMP_PUBLIC_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    response = requests.post(SENDCHAMP_API_URL, json=sms_data, headers=headers)

    if response.status_code != 200:
        error_details = response.text
        print("Error details:", error_details)
        raise HTTPException(status_code=400, detail="Failed to send OTP SMS")

    return {"message": "OTP sent successfully via SMS"}


@router.post("/password-reset/verify-otp", status_code=status.HTTP_200_OK)
async def verify_password_reset_otp(
    otp_code: str = Form(...),  # OTP input from the user
    email: str = Form(...),  # User's email to identify the record
    db: AsyncSession = Depends(get_async_db)
):
    async with db as session:
        # Query the password reset record for the given email and OTP
        query = (
            select(PasswordReset)
            .join(User, User.id == PasswordReset.user_id)
            .where(
                User.email == email,
                PasswordReset.otp_code == otp_code,
                PasswordReset.expires_at > datetime.utcnow(),  # Check if OTP is not expired
                PasswordReset.used == False  # Ensure OTP hasn't been used
            )
        )
        result = await session.execute(query)
        password_reset = result.scalar()

        if not password_reset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP."
            )

    return {"message": "OTP verified successfully. You may now reset your password."}
