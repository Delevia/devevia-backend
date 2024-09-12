from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from datetime import datetime
from ..schemas import LoginSchema, PhoneNumberRequest, OTPVerificationRequest
from ..utils.otp import verify_otp
from ..models import User, RefreshToken
from ..twilio_client import client, verify_service_sid  # Import the client and verify service SID
from ..schemas import RefreshTokenRequest, RequestTokenResponse
from ..schemas import pwd_context
from ..utils.security import  (
    create_access_token,
    create_refresh_token,
    verify_password,
    decode_refresh_token
) 

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
    user_data = decode_refresh_token(request.refresh_token, db)

    if not user_data:
        print("Failed to decode refresh token or token is invalid")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    access_token = create_access_token(data={"sub": str(user_data["sub"])})

    print(f"New access token generated: {access_token}")
    return {"access_token": access_token, "token_type": "bearer"}



# SEND OTP
@router.post("/send-otp/")
async def send_otp(request: PhoneNumberRequest):
    phone_number = request.phone_number
    try:
        verification = client.verify.services(verify_service_sid).verifications.create(
            to=phone_number,
            channel="sms"
        )
        return {"message": "OTP sent successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


# VERIFY OTP
@router.post("/verify-otp/")
async def verify_otp_code(request: OTPVerificationRequest, db: Session = Depends(get_db)):
    if verify_otp(db, request.phone_number, request.otp):
        return {"message": "OTP verified successfully."}
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP or OTP expired.")
