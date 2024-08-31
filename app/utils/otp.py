# utils/otp.py
from twilio.rest import Client
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import OTPVerification
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Twilio client
def initialize_twilio():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    return Client(account_sid, auth_token)

def generate_otp():
    """Generate a 6-digit OTP."""
    return random.randint(100000, 999999)

def send_otp(phone_number, otp):
    """Send the OTP to the user's phone number using Twilio."""
    client = initialize_twilio()
    message = client.messages.create(
        body=f"Your OTP code is {otp}",
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        to=phone_number
    )
    return message.sid

def store_otp(db: Session, phone_number: str, otp: str):
    """Store OTP in the database."""
    expires_at = datetime.utcnow() + timedelta(minutes=5)  # OTP expires in 5 minutes
    otp_entry = OTPVerification(phone_number=phone_number, otp_code=otp, expires_at=expires_at)
    db.add(otp_entry)
    db.commit()

def verify_otp(db: Session, phone_number: str, otp: str):
    """Verify the OTP against the database."""
    otp_entry = db.query(OTPVerification).filter_by(phone_number=phone_number, otp_code=otp).first()
    if otp_entry and not otp_entry.is_verified and otp_entry.expires_at > datetime.utcnow():
        otp_entry.is_verified = True
        db.commit()
        return True
    return False
