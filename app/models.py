from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum as SQLAEnum, TIMESTAMP, Date, LargeBinary, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy.sql.expression import text
from .enums import UserType, UserStatusEnum, PaymentMethodEnum, RideStatusEnum, RideTypeEnum, WalletTransactionEnum, OTPTypeEnum, GenderEnum
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func  # Import func to use for timestamp
import uuid
from sqlalchemy.dialects.postgresql import UUID



Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True, nullable=False)
    user_name = Column(String, index=True, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    address = Column(String(100), nullable=True)
    user_type = Column(SQLAEnum(UserType), nullable=False)
    user_status = Column(SQLAEnum(UserStatusEnum), default=UserStatusEnum.AWAITING, nullable=False)
    gender = Column(SQLAEnum(GenderEnum), nullable=True)  # Gender added here

    

    
    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    kyc = relationship("KYC", uselist=False, back_populates="user")
    rider = relationship("Rider", back_populates="user", uselist=False)
    driver = relationship("Driver", back_populates="user", uselist=False)
    wallet = relationship("Wallet", uselist=False, back_populates="user")
    # Chat relationships
    sent_messages = relationship("ChatMessage", foreign_keys="[ChatMessage.sender_id]", back_populates="sender")
    received_messages = relationship("ChatMessage", foreign_keys="[ChatMessage.receiver_id]", back_populates="receiver")
    password_resets = relationship("PasswordReset", back_populates="user")



class Referral(Base):
    __tablename__ = 'referrals'
    
    id = Column(Integer, primary_key=True, index=True)
    referrer_rider_id = Column(Integer, ForeignKey('riders.id'), nullable=True)  # Referring rider
    referrer_driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)  # Referring driver
    referred_rider_id = Column(Integer, ForeignKey('riders.id'), nullable=False)  # Referred rider
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Timestamp for when referral occurred

    # Relationships
    referrer_rider = relationship("Rider", foreign_keys=[referrer_rider_id], back_populates="referrals_made_by_rider")
    referrer_driver = relationship("Driver", foreign_keys=[referrer_driver_id], back_populates="referrals_made_by_driver")
    referred_rider = relationship("Rider", foreign_keys=[referred_rider_id], back_populates="referred_by")


class Rider(Base):
    __tablename__ = "riders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    rider_photo = Column(String, nullable=True)
    referral_code = Column(String(10), unique=True, nullable=True)  # UUID string for referral code
    nin = Column(String(11), nullable=True)  
    nin_photo = Column(String, nullable=True)  # Binary data for NIN photo added here
    ssn_number = Column(String, nullable=True, unique=True) 
    
    # Relationships
    user = relationship("User", back_populates="rider")
    rides = relationship("Ride", back_populates="rider")
    ratings = relationship("Rating", back_populates="rider")
    payment_methods = relationship("PaymentMethod", back_populates="rider")
    
    # Referral relationships
    referrals_made_by_rider = relationship("Referral", foreign_keys=[Referral.referrer_rider_id], back_populates="referrer_rider")
    referred_by = relationship("Referral", foreign_keys=[Referral.referred_rider_id], back_populates="referred_rider")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    driver_photo = Column(String, nullable=True)
    license_number = Column(String, unique=True, index=True, )
    license_expiry = Column(Date, nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    vehicle_name = Column(String,  nullable=True)  
    vehicle_model = Column(String, nullable=True)
    vehicle_insurance_policy = Column(String,  nullable=True)  
    vehicle_exterior_color = Column(String,  nullable=True)  
    vehicle_interior_color = Column(String, nullable=True)  
    referral_code = Column(String, unique=True, nullable=True)  
    nin_photo = Column(String,  nullable=True)  
    nin_number = Column(String, unique=True, nullable=True)
    proof_of_ownership = Column(String, nullable=True)  
    ssn_number = Column(String, nullable=True, unique=True) 
    ssn_photo = Column(String, nullable=True) 
    vehicle_inspection_approval = Column(String, nullable=True)


    # Relationships
    vehicle = relationship("Vehicle", back_populates="driver", uselist=False)
    user = relationship("User", back_populates="driver")
    rides = relationship("Ride", back_populates="driver")
    ratings = relationship("Rating", back_populates="driver")
    referrals_made_by_driver = relationship("Referral", foreign_keys=[Referral.referrer_driver_id], back_populates="referrer_driver")


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
    messages = relationship("ChatMessage", back_populates="ride")


# OTP Verification Model
class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    otp_code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_verified = Column(Boolean, default=False)
    hashed_password = Column(String, nullable=False)
    referral_code = Column(String, nullable=True)
    otp_type = Column(SQLAEnum(OTPTypeEnum), nullable=True)  # New field for OTP type
  


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
    company_wallet = relationship("CompanyWallet", back_populates="transactions")
    company_wallet_id = Column(Integer, ForeignKey("company_wallet.id"), nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey('rides.id'))  # Optional: Associate with a ride
    sender_id = Column(Integer, ForeignKey('users.id'))  # Either rider or driver
    receiver_id = Column(Integer, ForeignKey('users.id'))  # Either rider or driver
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    ride = relationship("Ride", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


# Company Wallet
class CompanyWallet(Base):
    __tablename__ = 'company_wallet'
    
    id = Column(Integer, primary_key=True, index=True)
    balance = Column(Float, default=0.0)
    account_number = Column(String, unique=True, nullable=False)  # New column for account number
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationship with transactions
    transactions = relationship("Transaction", back_populates="company_wallet")    



class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    otp_code = Column(String(6), nullable=False)  # Store the 6-digit OTP
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    used = Column(Boolean, default=False, nullable=False)  # Mark whether the reset token is used

    # Relationships
    user = relationship("User", back_populates="password_resets")