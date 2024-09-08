from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
from typing import Any, Optional
from sqlalchemy.orm import Session
from datetime import date
from ..database import get_db
from ..models import User, Rider, Driver, KYC, Admin
from ..schemas import KycCreate, AdminCreate, get_password_hash
from ..enums import PaymentMethodEnum

router = APIRouter()

# Rider Signup Endpoint
@router.post("/signup/rider/", status_code=status.HTTP_201_CREATED)
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
    existing_user = db.query(User).filter(User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone Number already exists")
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="email already exists")
    existing_user = db.query(User).filter(User.user_name == user_name).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="user name already exists")
    
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
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

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
    db: Session = Depends(get_db)
):
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
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    file_content = await driver_photo.read()
    db_driver = Driver(
        user_id=db_user.id,
        license_number=license_number,
        license_expiry=license_expiry,
        years_of_experience=years_of_experience,
        driver_photo=file_content
    )
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)

    return {"message": "Registration Successful"}


# Create a KYC
@router.post("/kyc/", status_code=status.HTTP_201_CREATED)
def create_kyc(kyc: KycCreate, db: Session = Depends(get_db)) -> Any:
    existing_kyc = db.query(KYC).filter(KYC.user_id == kyc.user_id).first()
    if existing_kyc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="KYC record already exists for this user."
        )

    existing_identity = db.query(KYC).filter(KYC.identity_number == kyc.identity_number).first()
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
    db.commit()
    db.refresh(new_kyc)

    return {"message": "KYC record created successfully", "kyc_id": new_kyc.kyc_id}


# Create Admin Endpoint
@router.post("/admin/", status_code=status.HTTP_201_CREATED)
def create_admin(admin: AdminCreate, db: Session = Depends(get_db)) -> Any:
    user = db.query(User).filter(User.id == admin.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_admin = Admin(
        user_id=admin.user_id,
        department=admin.department,
        access_level=admin.access_level
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {"message": "Admin record created successfully", "admin_id": new_admin.id}
