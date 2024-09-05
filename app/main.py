from fastapi import FastAPI, status, HTTPException, Depends, Form, UploadFile, File
from . import models
from .enums import PaymentMethodEnum
from typing import Any, Optional
from datetime import date
from .database import engine, get_db
from sqlalchemy.orm import Session
from .models import User, Rider, Driver, KYC, Admin
from .schemas import RiderCreate, DriverCreate, create_user, PhoneNumberRequest, OTPVerificationRequest, KycCreate, AdminCreate, get_password_hash 
from .utils.otp import generate_otp, send_otp, store_otp, verify_otp
from .twilio_client import client, twilio_phone_number, verify_service_sid  # Import the client and phone number


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello, FastAPI!"}


# Rider Signup Endpoint
@app.post("/signup/rider/", status_code=status.HTTP_201_CREATED)
async def signup_rider(
    full_name: str = Form(...),
    user_name: str = Form(...),
    phone_number: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    address: Optional[str] = Form(None),
    prefered_payment_method: PaymentMethodEnum = Form(...),
    rider_photo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Check if user already exists
    existing_user = db.query(User).filter(User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone Number already exists")
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="email already exists")
    existing_user = db.query(User).filter(User.user_name == user_name).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="user name already exists")
        
    

    # Hash the password
    hashed_password = get_password_hash(password)

    # Create new user
    db_user = User(
        full_name=full_name,
        user_name=user_name,
        phone_number=phone_number,
        email=email,
        hashed_password=hashed_password,
        address=address,
        user_type="RIDER"  # Ensure the user_type is set correctly
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Save the uploaded file
    file_content = await rider_photo.read()
    db_rider = Rider(
        user_id=db_user.id,
        rider_photo=file_content,
        prefered_payment_method=prefered_payment_method
    )
    db.add(db_rider)
    db.commit()
    db.refresh(db_rider)

    return {"message": "Registration Successful"}




# Driver Signup Endpoint
@app.post("/signup/driver/", status_code=status.HTTP_201_CREATED)
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
    db: Session = Depends(get_db)
):
    # Check if user already exists
    existing_license = db.query(Driver).filter(Driver.license_number == license_number).first()
    if existing_license:
        raise HTTPException(status_code=400, detail="License number already exists")
    existing_user = db.query(User).filter(User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already exists")
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")
    existing_user = db.query(User).filter(User.user_name == user_name).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Hash the password
    hashed_password = get_password_hash(password)

    # Create new user
    db_user = User(
        full_name=full_name,
        user_name=user_name,
        phone_number=phone_number,
        email=email,
        hashed_password=hashed_password,
        address=address,
        user_type="DRIVER"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Save the uploaded file to a specific directory
    file_content = await driver_photo.read()

    # Save the uploaded file to a specific directory
    # file_location = f"files/{driver_photo.filename}"
    # try:
    #     with open(file_location, "wb") as file_object:
    #         file_object.write(await driver_photo.read())
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

    # Create driver profile
    db_driver = Driver(
        user_id=db_user.id,
        license_number=license_number,
        license_expiry=license_expiry,
        years_of_experience=years_of_experience,
        driver_photo=file_content  # Store the file path in the database
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


# Create a KYC
@app.post("/kyc/", status_code=status.HTTP_201_CREATED)
def create_kyc(kyc: KycCreate, db: Session = Depends(get_db)) -> Any:
    # Check if the user already has a KYC record
    existing_kyc = db.query(KYC).filter(KYC.user_id == kyc.user_id).first()
    if existing_kyc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="KYC record already exists for this user."
        )

    # Check if the identity number already exists
    existing_identity = db.query(KYC).filter(KYC.identity_number == kyc.identity_number).first()
    if existing_identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identity number already exists."
        )

    # Create a new KYC record
    new_kyc = KYC(
        user_id=kyc.user_id,
        identity_number=kyc.identity_number
    )
    db.add(new_kyc)
    db.commit()
    db.refresh(new_kyc)

    return {"message": "KYC record created successfully", "kyc_id": new_kyc.kyc_id}


# Create Admin Endpoint
@app.post("/admin/", status_code=status.HTTP_201_CREATED)
def create_admin(admin: AdminCreate, db: Session = Depends(get_db)) -> Any:
    # Check if the user exists
    user = db.query(User).filter(User.id == admin.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create a new admin record
    new_admin = Admin(
        user_id=admin.user_id,
        department=admin.department,
        access_level=admin.access_level
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {"message": "Admin record created successfully", "admin_id": new_admin.id}


