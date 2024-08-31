from fastapi import FastAPI, status, HTTPException, Depends
from . import models
from .database import engine, get_db
from sqlalchemy.orm import Session
from .models import User, Rider, Driver
from .schemas import RiderCreate, DriverCreate, create_user, PhoneNumberRequest, OTPVerificationRequest
from .utils.otp import generate_otp, send_otp, store_otp, verify_otp
from .twilio_client import client, twilio_phone_number, verify_service_sid  # Import the client and phone number


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello, FastAPI!"}

# Rider Signup Endpoint
@app.post("/signup/rider/", status_code=status.HTTP_201_CREATED)
def signup_rider(rider: RiderCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.phone_number == rider.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone Number already exists")

    # Create new user
    db_user = create_user(db=db, user=rider)

    # Create rider profile
    db_rider = Rider(user_id=db_user.id)
    db.add(db_rider)
    db.commit()
    db.refresh(db_rider)

    return {"message": "Registration Successful"}

# Driver Signup Endpoint
@app.post("/signup/driver/", status_code=status.HTTP_201_CREATED)
def signup_driver(driver: DriverCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.phone_number == driver.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone Number already exists")

    # Create new user
    db_user = create_user(db=db, user=driver)

    # Create driver profile
    db_driver = Driver(user_id=db_user.id,
                        license_number=driver.license_number,
                        license_expiry=driver.license_expiry,
                        years_of_experience=driver.years_of_experience
                        )
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)

    return {"message": "Registration Successful"}



# @app.put("/users/{user_id}/status/", response_model=UserBase)
# def update_user_status(user_id: int, status: UserStatusEnum, db: Session = Depends(get_db)):
#     user = db.query(Users).filter(Users.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
    
#     user.user_status = status
#     db.commit()
#     db.refresh(user)
    
#     return user

# SEND OTP
@app.post("/send-otp/")
async def send_otp(request: PhoneNumberRequest):
    phone_number = request.phone_number

    try:
        # Create a verification request with Twilio Verify
        verification = client.verify.services(verify_service_sid).verifications.create(
            to=phone_number,
            channel="sms"  # Can be 'call' or 'email' depending on your use case
        )
        
        return {"message": "OTP sent successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


# VERIFY OTP
@app.post("/verify-otp/")
async def verify_otp_code(request: OTPVerificationRequest, db: Session = Depends(get_db)):
    if verify_otp(db, request.phone_number, request.otp):
        return {"message": "OTP verified successfully."}
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP or OTP expired.")