


from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum as SQLAEnum, TIMESTAMP, Date, Integer, LargeBinary, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy.sql.expression import text
from .enums import UserType, UserStatusEnum, PaymentMethodEnum
from datetime import datetime

# Base User Model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True, nullable=False)
    user_name = Column(String, index=True, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    address = Column(String(100), nullable=False)
    user_type = Column(SQLAEnum(UserType), nullable=False)  # Adding the Enum column
    user_status = Column(SQLAEnum(UserStatusEnum), default=UserStatusEnum.AWAITING, nullable=False)  
   



    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    kyc = relationship("KYC", uselist=False, back_populates="user")
    rider = relationship("Rider", back_populates="user", uselist=False, cascade="all, delete-orphan")
    driver = relationship("Driver", back_populates="user", uselist=False, cascade="all, delete-orphan")

# Rider Model
class Rider(Base):
    __tablename__ = "riders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    rider_photo = Column(LargeBinary, nullable=True)  # Store image as binary data (BLOB)
    prefered_payment_method = Column(SQLAEnum(PaymentMethodEnum), nullable=False)  # Correctly define the Enum type here
    # Add any rider-specific fields here

    user = relationship("User", back_populates="rider")
    rides = relationship("Ride", back_populates="rider")

# Driver Model
class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    driver_photo = Column(LargeBinary, nullable=True)  # Store image as binary data (BLOB)
    license_number = Column(String, unique=True, index=True)
    license_expiry = Column(Date, nullable=False)  # Optional field for license expiry date
    years_of_experience = Column(Integer, nullable=False)  # Optional field for years of experience

    vehicle = relationship("Vehicle", back_populates="driver", uselist=False)
    user = relationship("User", back_populates="driver")
    rides = relationship("Ride", back_populates="driver")

# Vehicle Model
class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), unique=True)  # Ensure this is unique
    make = Column(String, index=True)
    model = Column(String, index=True)
    year = Column(Integer)
    license_plate = Column(String, unique=True, index=True)
    color = Column(String, index=True)
    vehicle_number = Column(String, index=True)
    last_service_date = Column(String, index=True)
    vehicle_status = Column(String, index=True)

    driver = relationship("Driver", back_populates="vehicle", uselist=False)

# Ride Model
class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)
    rider_id = Column(Integer, ForeignKey("riders.id"))
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    pickup_location = Column(String)
    dropoff_location = Column(String)
    fare = Column(Float)
    status = Column(String, default="requested")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))

    rider = relationship("Rider", back_populates="rides")
    driver = relationship("Driver", back_populates="rides")


# OTP Verification Model
class OTPVerification(Base):
    __tablename__ = "otp_verification"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, nullable=False)  # Foreign key to User model
    otp_code = Column(String, nullable=False)  # The generated OTP code
    is_verified = Column(Boolean, default=False)  # Whether the OTP has been verified
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)  # Expiry timestamp for the OTP





# OTP Admin Model
class Admin(Base):
    __tablename__ = "admin"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    department = Column(String, nullable=False)  
    access_level = Column(String, nullable=False)


class KYC(Base):
    __tablename__ = "kyc"

    kyc_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    identity_number = Column(String, unique=True, nullable=False)

    # Establish a relationship with the User model
    user = relationship("User", back_populates="kyc")



class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)  # Store the actual token string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Assume the user table is 'users'
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)  # Flag to indicate if the token is revoked

    user = relationship("User", back_populates="refresh_tokens")  # Relationship with the User model


# BlacklistedToken
class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)