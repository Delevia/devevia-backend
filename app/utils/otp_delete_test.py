import asyncio
from datetime import datetime, timedelta
# Import your database session dependency and model
from app.database import get_async_db  # Update with your actual path
from app.models import OTPVerification  # Update with your actual path
from sqlalchemy import delete

# async def test_delete_expired_otps():
    # Use async for to iterate over the async generator (get_async_db)
    # async for db in get_async_db():  # Use async for instead of async with
        # expiration_threshold = datetime.utcnow() - timedelta(minutes=5)
        # print(f"Deleting OTPs older than: {expiration_threshold}")
        
        # Execute deletion query
        # result = await db.execute(
        #     delete(OTPVerification).where(OTPVerification.expires_at <= expiration_threshold)
        # )
        # await db.commit()
        
        # deleted_count = result.rowcount if result else 0
        # print(f"Deleted {deleted_count} expired OTP(s).")

# Run the test
# asyncio.run(test_delete_expired_otps())


async def delete_expired_otps():
    """
    Deletes expired OTPs from the database.
    """
    async for db in get_async_db():  # Using async for to iterate over the async generator (get_async_db)
        expiration_threshold = datetime.utcnow() - timedelta(minutes=5)
        print(f"Deleting OTPs older than: {expiration_threshold}")
        
        # Execute deletion query
        result = await db.execute(
            delete(OTPVerification).where(OTPVerification.expires_at <= expiration_threshold)
        )
        await db.commit()
        
        deleted_count = result.rowcount if result else 0
        print(f"Deleted {deleted_count} expired OTP(s).")

    await delete_expired_otps()
        