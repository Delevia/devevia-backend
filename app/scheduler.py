# main.py
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from .database import get_async_db  # Adjust as needed
from .models import OTPVerification
from sqlalchemy.future import select

app = FastAPI()

async def delete_expired_otps():
    """Delete OTP records that have expired (5 minutes after expiration) regardless of verification status."""
    async with get_async_db() as session:
        threshold_time = datetime.utcnow() - timedelta(minutes=5)
        expired_otps = await session.execute(
            select(OTPVerification)
            .filter(OTPVerification.expires_at < threshold_time)
        )
        for otp_entry in expired_otps.scalars():
            await session.delete(otp_entry)
        await session.commit()

def start_scheduler():
    """Start the APScheduler to run the cleanup job every 5 minutes."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(delete_expired_otps, "interval", minutes=5)  # Run every 5 minutes
    scheduler.start()

