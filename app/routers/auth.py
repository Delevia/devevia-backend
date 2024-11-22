from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_db  # Ensure to update this to get the async session
from ..schemas import LoginSchema
from ..models import User, RefreshToken, BlacklistedToken, Rider
from ..schemas import RefreshTokenRequest, RequestTokenResponse, LogoutRequest
from ..schemas import pwd_context
from dotenv import load_dotenv
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







load_dotenv()


# Configure SendGrid API key
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_EMAIL_SENDER = "no-reply@delevia.com"  # Use your verified SendGrid sender email

# Configue Sendchamp
SENDCHAMP_API_URL = os.getenv("SENDCHAMP_API_URL")
SENDCHAMP_PUBLIC_KEY = os.getenv("SENDCHAMP_PUBLIC_KEY")

router = APIRouter()

# Reusable function to verify password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# Rider LOgin Endpoint
@router.post("/login/rider/", status_code=status.HTTP_200_OK)
async def login_rider(
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_async_db)
):
    # Query the user with the phone number and ensure user_type is "RIDER"
    async with db as session:
        result = await session.execute(
            select(User)
            .options(joinedload(User.rider))  # Eager load the rider relationship
            .filter(User.phone_number == login_data.phone_number, User.user_type == "RIDER")
        )
        user = result.scalar()  # Fetch the user object

    # Validate the user's existence and password
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")

    # The rider is already loaded, so we don't hit the DetachedInstanceError
    rider = user.rider

    if not rider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider not found")

    # Generate tokens for the rider
    access_token = create_access_token(data={"sub": str(rider.id)})
    refresh_token = create_refresh_token(data={"sub": str(rider.id)}, db=db)
     # Prepare the response data
    user_data = jsonable_encoder(user)  # Serialize the user data
    user_data.pop("hashed_password", None)  # Remove sensitive fields if needed

    # Return a response with rider ID and tokens
    return {
        "message": "Login Successful",
        "user_type": user.user_type,  # User type should be "DRIVER"
        "rider_id": rider.id,  # Return the rider ID here
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_data": user_data  # Include user data in the response

    }

# Driver Login Endpoint
@router.post("/login/driver/", status_code=status.HTTP_200_OK)
async def login_driver(
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_async_db)
):
    # Query the user with the phone number and ensure user_type is "DRIVER"
    async with db as session:
        result = await session.execute(
            select(User)
            .options(joinedload(User.driver))  # Eager load the driver relationship
            .filter(User.phone_number == login_data.phone_number, User.user_type == "DRIVER")
        )
        user = result.scalar()  # Fetch the user object

    # Validate the driver's existence and password
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")

    # Get the associated driver from the user
    driver = user.driver

    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    # Generate tokens for the driver
    access_token = create_access_token(data={"sub": str(driver.id)})
    refresh_token = create_refresh_token(data={"sub": str(driver.id)}, db=db)  # Add await for async call
    user_data = jsonable_encoder(user)  # Serialize the user data
    user_data.pop("hashed_password", None)  # Remove sensitive fields if needed


    # Return a response with driver ID and tokens
    return {
        "message": "Login Successful",
        "user_type": user.user_type,  # User type should be "DRIVER"
        "driver_id": driver.id,  # Return the driver ID here
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_data": user_data  # Include user data in the response

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
