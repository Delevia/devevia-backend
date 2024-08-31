# app/twilio_client.py

import os
from twilio.rest import Client
from dotenv import load_dotenv  # Import load_dotenv from python-dotenv


# Load environment variables from the .env file
load_dotenv()


# Fetch credentials from environment variables
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
verify_service_sid = os.getenv('TWILIO_VERIFY_SERVICE_SID')


# Ensure credentials are present
if not all([account_sid, auth_token, twilio_phone_number]):
    raise ValueError("Twilio credentials are not set properly")

# Initialize the Twilio client
client = Client(account_sid, auth_token)
