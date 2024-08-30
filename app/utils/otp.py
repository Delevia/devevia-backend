# utils/otp.py
from twilio.rest import Client
import random
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
    return random.randint(100000, 999999)

def send_otp(phone_number, otp):
    client = initialize_twilio()
    message = client.messages.create(
        body=f"Your OTP code is {otp}",
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        to=phone_number
    )
    return message.sid

# In-memory storage for OTPs (replace with a database in production)
otp_storage = {}

def store_otp(phone_number, otp):
    otp_storage[phone_number] = otp

def verify_otp(phone_number, otp):
    stored_otp = otp_storage.get(phone_number)
    if stored_otp == otp:
        del otp_storage[phone_number]  # OTP should be used only once
        return True
    return False
