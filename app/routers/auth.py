from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from datetime import datetime
from ..schemas import LoginSchema,OTPVerificationRequest
# from ..utils.otp import verify_otp
from ..models import User, RefreshToken, BlacklistedToken
from ..schemas import RefreshTokenRequest, RequestTokenResponse, LogoutRequest
from ..schemas import pwd_context
from dotenv import load_dotenv
import os
import requests
from ..utils.otp import generate_otp, OTPVerification, generate_otp_expiration
from ..utils.schemas_utils import OtpPhoneNumberRequest
from ..utils.security import  (
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
    db: Session = Depends(get_db)
):
    rider = db.query(User).filter(User.phone_number == login_data.phone_number, User.user_type == "RIDER").first()
    if not rider or not verify_password(login_data.password, rider.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")

    access_token = create_access_token(data={"sub": str(rider.id)})  # Ensure sub is a string
    refresh_token = create_refresh_token(data={"sub": str(rider.id)}, db=db)  # Pass db session here

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
    db: Session = Depends(get_db)
):
    driver = db.query(User).filter(User.phone_number == login_data.phone_number, User.user_type == "DRIVER").first()
    if not driver or not verify_password(login_data.password, driver.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")
    
    access_token = create_access_token(data={"sub": str(driver.id)})  # Ensure sub is a string
    refresh_token = create_refresh_token(data={"sub": str(driver.id)}, db=db)  # Pass db session here

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
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    print(f"Received refresh token: {request.refresh_token}")

    # Check if the refresh token is blacklisted
    blacklisted_token = db.query(BlacklistedToken).filter(BlacklistedToken.token == request.refresh_token).first()
    if blacklisted_token:
        print("Refresh token is blacklisted")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Decode the refresh token
    user_data = decode_refresh_token(request.refresh_token, db)

    if not user_data:
        print("Failed to decode refresh token or token is invalid")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Generate a new access token
    access_token = create_access_token(data={"sub": str(user_data["sub"])})

    print(f"New access token generated: {access_token}")
    return {"access_token": access_token, "token_type": "bearer"}



# SEND OTP
@router.post("/send-otp/")
async def send_otp(request: OtpPhoneNumberRequest, db: Session = Depends(get_db)):
    phone_number = request.phone_number

    # Generate OTP and expiration time
    otp_code = generate_otp()
    expiration_time = generate_otp_expiration()

    # Create OTP entry in the database
    otp_entry = OTPVerification(
        phone_number=phone_number,
        otp_code=otp_code,
        expires_at=expiration_time
    )
    db.add(otp_entry)   # Add OTP to the database session
    db.commit()         # Commit the transaction to save OTP
    db.refresh(otp_entry)  # Refresh the instance to get updated information

    # Send the OTP via SmartSMS
    payload = {
        'token': API_KEY,
        'sender': SENDER_ID,
        'to': phone_number,
        'message': f"Your Delevia OTP is {otp_code}. It expires in 5 minutes.",
        'type': '0',  # 0 for text message
        'routing': '3',  # Set routing
        'ref_id': 'unique-ref-id',  # Replace if needed
        'simserver_token': '',
        'dlr_timeout': '',
        'schedule': ''
    }

    response = requests.post(SMART_SMS_API_URL, data=payload)
    print(response.status_code)
    print(response.text)

    # Check if the SMS was sent successfully
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to send OTP")

    return {"message": "OTP sent successfully"}



# VERIFY OTP
# @router.post("/verify-otp/")
# async def verify_otp_code(request: OTPVerificationRequest, db: Session = Depends(get_db)):
#     if verify_otp(db, request.phone_number, request.otp):
#         return {"message": "OTP verified successfully."}
#     else:
#         raise HTTPException(status_code=400, detail="Invalid OTP or OTP expired.")


#Logout Endpoint
@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    # Retrieve the refresh token from the request body
    refresh_token = request.refresh_token

    # Find the refresh token in the database
    token_record = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()

    if not token_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refresh token not found")

    # Mark the refresh token as revoked
    token_record.is_revoked = True
    db.commit()

    # Blacklist the refresh token
    blacklisted_refresh_token = BlacklistedToken(token=refresh_token)
    db.add(blacklisted_refresh_token)

    # Optionally, blacklist the access token if provided
    if request.access_token:
        blacklisted_access_token = BlacklistedToken(token=request.access_token)
        db.add(blacklisted_access_token)

    # Commit all changes at once
    db.commit()

    return {"message": "Logout successful"}