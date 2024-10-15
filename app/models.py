from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum as SQLAEnum, TIMESTAMP, Date, LargeBinary, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy.sql.expression import text
from .enums import UserType, UserStatusEnum, PaymentMethodEnum, RideStatusEnum, RideTypeEnum, WalletTransactionEnum
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# User Model
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
    user_type = Column(SQLAEnum(UserType), nullable=False)
    user_status = Column(SQLAEnum(UserStatusEnum), default=UserStatusEnum.AWAITING, nullable=False)

    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    kyc = relationship("KYC", uselist=False, back_populates="user")
    rider = relationship("Rider", back_populates="user", uselist=False)
    driver = relationship("Driver", back_populates="user", uselist=False)
    wallet = relationship("Wallet", uselist=False, back_populates="user")

# Rider Model
class Rider(Base):
    __tablename__ = "riders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    rider_photo = Column(LargeBinary, nullable=True)
    
    user = relationship("User", back_populates="rider")
    rides = relationship("Ride", back_populates="rider")
    ratings = relationship("Rating", back_populates="rider")
    payment_methods = relationship("PaymentMethod", back_populates="rider")

# Driver Model
class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    driver_photo = Column(LargeBinary, nullable=True)
    license_number = Column(String, unique=True, index=True)
    license_expiry = Column(Date, nullable=False)
    years_of_experience = Column(Integer, nullable=False)
    
    vehicle = relationship("Vehicle", back_populates="driver", uselist=False)
    user = relationship("User", back_populates="driver")
    rides = relationship("Ride", back_populates="driver")
    ratings = relationship("Rating", back_populates="driver")

# Vehicle Model
class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), unique=True)
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
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    pickup_location = Column(String)
    dropoff_location = Column(String)
    fare = Column(Float, nullable=True)
    estimated_price = Column(Float, nullable=True)
    status = Column(SQLAEnum(RideStatusEnum), default=RideStatusEnum.INITIATED)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    ride_type = Column(SQLAEnum(RideTypeEnum), default=RideTypeEnum.STANDARD, nullable=False)
    payment_status = Column(String, default="PENDING")
    recipient_phone_number = Column(String(15), nullable=True)
    booking_for = Column(String, nullable=False, default='self')

    rider = relationship("Rider", back_populates="rides")
    driver = relationship("Driver", back_populates="rides")
    rating = relationship("Rating", uselist=False, back_populates="ride")

# OTP Verification Model
class OTPVerification(Base):
    __tablename__ = "otp_verification"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, nullable=False)
    otp_code = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)

# Admin Model
class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    department = Column(String, nullable=False)
    access_level = Column(String, nullable=False)

# KYC Model
class KYC(Base):
    __tablename__ = "kyc"

    kyc_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    identity_number = Column(String, unique=True, nullable=False)
    
    user = relationship("User", back_populates="kyc")

# Refresh Token Model
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="refresh_tokens")

# Blacklisted Token Model
class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Rating Model
class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    rider_id = Column(Integer, ForeignKey("riders.id"), nullable=False)
    rating = Column(Float, nullable=False)
    comment = Column(String, nullable=True)

    ride = relationship("Ride", back_populates="rating")
    driver = relationship("Driver", back_populates="ratings")
    rider = relationship("Rider", back_populates="ratings")

# Payment Method Model
class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    rider_id = Column(Integer, ForeignKey("riders.id"), nullable=False)
    payment_type = Column(SQLAEnum(PaymentMethodEnum), nullable=False)
    card_number = Column(String(16), nullable=True)
    expiry_date = Column(String(5), nullable=True)
    token = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)

    rider = relationship("Rider", back_populates="payment_methods")

# Wallet Model
class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    balance = Column(Float, default=0.0)
    account_number = Column(String, unique=True, nullable=False)  # Add this field

    
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")


# Transaction Model
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'))
    amount = Column(Float)
    transaction_type = Column(SQLAEnum(WalletTransactionEnum, name='wallet_transaction_enum'))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship("Wallet", back_populates="transactions")
