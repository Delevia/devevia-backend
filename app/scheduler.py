# main.py
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from .database import get_async_db
from .models import OTPVerification
from sqlalchemy.future import select
import asyncio
import logging

app = FastAPI()

# Set up basic logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def delete_expired_otps():
    """Delete OTP records that have expired (5 minutes after expiration) regardless of verification status."""
    logger.info(f"Running delete_expired_otps at {datetime.utcnow()}")
    async with get_async_db() as session:
        threshold_time = datetime.utcnow() - timedelta(minutes=5)
        expired_otps = await session.execute(
            select(OTPVerification)
            .filter(OTPVerification.expires_at < threshold_time)
        )
        for otp_entry in expired_otps.scalars():
            await session.delete(otp_entry)
        await session.commit()
    logger.info("Finished deleting expired OTPs.")

async def schedule_delete_expired_otps():
    """Helper function to ensure delete_expired_otps is properly awaited."""
    await delete_expired_otps()

def start_scheduler():
    """Start the APScheduler to run the cleanup job every 5 minutes."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(schedule_delete_expired_otps()), "interval", minutes=5)
    scheduler.start()

