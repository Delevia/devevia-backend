# utils/otp.py
from twilio.rest import Client
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import OTPVerification

# Generate OTP
def generate_otp(length: int = 6) -> str:
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

# Generate OTP expiration time
def generate_otp_expiration(minutes: int = 5) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)













