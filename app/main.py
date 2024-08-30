# from fastapi import FastAPI, HTTPException, Depends, status
# from sqlalchemy.orm import Session
# from . import models
# from .database import engine, get_db
# from .schemas import RiderCreate, DriverCreate, OTPVerification, UserCreate
from fastapi import FastAPI, status, HTTPException, Depends
from . import models
from .database import engine, get_db
from sqlalchemy.orm import Session
from .models import User, Rider, Driver
from .schemas import RiderCreate, DriverCreate, create_user
from .utils.otp import generate_otp, send_otp, store_otp, verify_otp

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.post("/register/rider/", status_code=status.HTTP_200_OK)
def register_rider(rider_data: RiderCreate, db: Session = Depends(get_db)):
    # Check if phone number is already registered
    existing_user = db.query(models.User).filter(models.User.phone_number == rider_data.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone Number already exists")

    # Generate OTP
    otp = generate_otp()

    # Send OTP via SMS
    send_otp(rider_data.phone_number, otp)

    # Store OTP for later verification
    store_otp(rider_data.phone_number, otp)

    return {"message": "Registration details received. OTP sent to your phone."}


@app.post("/register/driver/", status_code=status.HTTP_200_OK)
def register_driver(driver_data: DriverCreate, db: Session = Depends(get_db)):
    # Check if phone number is already registered
    existing_user = db.query(models.User).filter(models.User.phone_number == driver_data.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone Number already exists")

    # Generate OTP
    otp = generate_otp()

    # Send OTP via SMS
    send_otp(driver_data.phone_number, otp)

    # Store OTP for later verification
    store_otp(driver_data.phone_number, otp)

    return {"message": "Registration details received. OTP sent to your phone."}


@app.post("/verify/rider/", status_code=status.HTTP_201_CREATED)
def verify_rider_otp_and_register(phone_number: str, otp: int, rider_data: RiderCreate, db: Session = Depends(get_db)):
    # Verify OTP
    if not verify_otp(phone_number, otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Create new user
    db_user = models.User(phone_number=rider_data.phone_number, name=rider_data.name, user_type='RIDER')
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Create rider profile
    db_rider = models.Rider(user_id=db_user.id)
    db.add(db_rider)
    db.commit()

    return {"message": "Registration successful"}

@app.post("/verify/driver/", status_code=status.HTTP_201_CREATED)
def verify_driver_otp_and_register(phone_number: str, otp: int, driver_data: DriverCreate, db: Session = Depends(get_db)):
    # Verify OTP
    if not verify_otp(phone_number, otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Create new user
    db_user = models.User(phone_number=driver_data.phone_number, name=driver_data.name, user_type='DRIVER')
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Create driver profile
    db_driver = models.Driver(
        user_id=db_user.id,
        license_number=driver_data.license_number,
        license_expiry=driver_data.license_expiry,
        years_of_experience=driver_data.years_of_experience
    )
    db.add(db_driver)
    db.commit()

    return {"message": "Registration successful"}

