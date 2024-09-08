from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import LoginSchema, PhoneNumberRequest, OTPVerificationRequest
from ..utils.otp import verify_otp
from ..models import User
from ..twilio_client import client, verify_service_sid  # Import the client and verify service SID
from ..schemas import pwd_context

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

    return {"message": "Login Successful", "user_id": rider.id, "user_type": rider.user_type}


# Driver Login Endpoint
@router.post("/login/driver/", status_code=status.HTTP_200_OK)
async def login_driver(
    login_data: LoginSchema,
    db: Session = Depends(get_db)
):
    driver = db.query(User).filter(User.phone_number == login_data.phone_number, User.user_type == "DRIVER").first()
    if not driver or not verify_password(login_data.password, driver.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid phone number or password")

    return {"message": "Login Successful", "user_id": driver.id, "user_type": driver.user_type}


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
