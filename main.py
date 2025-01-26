from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from datetime import datetime, timedelta
import logging
from app.routers import auth, users, rides, wallet, chatMessage, pushNotifications,coordinates

from app.database import Base, async_engine, get_async_db
from app.models import Ride, ChatMessage, CallLog
from app.utils.connection_manager import ConnectionManager, CallConnectionManager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.utils.otp_delete_test import delete_expired_otps
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your specific frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# WebSocket Connection Manager
manager = ConnectionManager()
call_manager = CallConnectionManager()
# Set up the scheduler
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    """
    Start the scheduler to periodically delete expired OTPs.
    """
    logger.info("Starting scheduler for OTP cleanup...")

    # Schedule the OTP cleanup task to run every 2 minutes
    scheduler.add_job(
        delete_expired_otps,  # Function to run
        trigger=IntervalTrigger(minutes=2),  # Every 2 minutes
        id="otp_cleanup",  # Job id
        name="Delete expired OTPs",  # Job name
        replace_existing=True  # Replace the job if it already exists
    )

    # Start the scheduler
    scheduler.start()
    logger.info("OTP cleanup task scheduled.")

@app.on_event("shutdown")
async def shutdown_scheduler():
    """
    Shutdown the scheduler gracefully when the app shuts down.
    """
    logger.info("Shutting down scheduler...")

    # Ensure the event loop is still running
    if scheduler._eventloop and scheduler._eventloop.is_running():
        scheduler.shutdown()
    else:
        logger.warning("Scheduler event loop is not running!")

    logger.info("Scheduler stopped.")

# Optional root endpoint to test the app
@app.get("/")
async def read_root():
    return {"message": "OTP Cleanup Service is running!"}


# WebSocket endpoint for chat within rides
@app.websocket("/ws/chat/{ride_id}/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    ride_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    """
    WebSocket endpoint for chat within a ride.
    """
    # Check if the ride exists
    result = await db.execute(select(Ride).filter_by(id=ride_id))
    ride = result.scalar()

    if not ride:
        await websocket.close(code=1008)
        raise HTTPException(status_code=404, detail="Ride not found")

    # Check if the user is authorized for the ride
    if ride.rider_id != user_id and ride.driver_id != user_id:
        await websocket.close(code=1008)
        raise HTTPException(status_code=403, detail="User not authorized for this ride")

    # Connect the user to the WebSocket manager
    await manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # Parse recipient_id and message (format: recipient_id:message)
            try:
                recipient_id, message = data.split(":", 1)
                recipient_id = int(recipient_id)
            except ValueError:
                await websocket.send_text("Invalid message format. Expected 'recipient_id:message'.")
                continue

            # Log and save the message
            chat_message = ChatMessage(
                sender_id=user_id,
                receiver_id=recipient_id,
                message=message,
                ride_id=ride_id
            )
            db.add(chat_message)
            await db.commit()

            # Send the message to the recipient
            if recipient_id in [ride.rider_id, ride.driver_id]:
                await manager.send_personal_message(f"User {user_id}: {message}", recipient_id)
            else:
                await websocket.send_text("Recipient not part of this ride.")

    except WebSocketDisconnect:
        await manager.disconnect(user_id)
        logger.info(f"User {user_id} disconnected from WebSocket.")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket: {e}")
        await websocket.close(code=1011)  # Close with a server error code



@app.websocket("/ws/call/{ride_id}/{user_id}")
async def websocket_call_endpoint(
    websocket: WebSocket,
    ride_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    """
    WebSocket endpoint for handling call functionality within a ride.
    """
    # Check if the ride exists
    result = await db.execute(select(Ride).filter_by(id=ride_id))
    ride = result.scalar()

    if not ride:
        await websocket.close(code=1008)
        raise HTTPException(status_code=404, detail="Ride not found")

    # Check if the user is authorized for the ride
    if ride.rider_id != user_id and ride.driver_id != user_id:
        await websocket.close(code=1008)
        raise HTTPException(status_code=403, detail="User not authorized for this ride")

    # Connect the user to the CallConnectionManager
    await call_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()

            event_type = data.get("event_type")
            recipient_id = data.get("recipient_id")
            payload = data.get("payload")

            if not recipient_id or recipient_id not in [ride.rider_id, ride.driver_id]:
                await websocket.send_json({"error": "Recipient not part of this ride."})
                continue

            # Handle different call events
            if event_type == "call_initiate":
                # Log the call initiation
                call_log = CallLog(
                    ride_id=ride_id,
                    caller_id=user_id,
                    receiver_id=recipient_id,
                    status="INITIATED"
                )
                db.add(call_log)
                await db.commit()

                # Notify the recipient
                await call_manager.send_personal_message(
                    {
                        "event_type": "call_initiate",
                        "from_user": user_id,
                        "message": "Incoming call.",
                        "payload": payload
                    },
                    recipient_id
                )

            elif event_type == "call_accept":
                # Update call log status
                call_log = await db.execute(
                    select(CallLog)
                    .filter_by(ride_id=ride_id, caller_id=recipient_id, receiver_id=user_id, status="INITIATED")
                )
                call_log = call_log.scalar()
                if call_log:
                    call_log.status = "ACCEPTED"
                    await db.commit()

                # Notify the caller
                await call_manager.send_personal_message(
                    {"event_type": "call_accept", "from_user": user_id, "message": "Call accepted."},
                    recipient_id
                )

            elif event_type == "call_reject":
                # Update call log status
                call_log = await db.execute(
                    select(CallLog)
                    .filter_by(ride_id=ride_id, caller_id=recipient_id, receiver_id=user_id, status="INITIATED")
                )
                call_log = call_log.scalar()
                if call_log:
                    call_log.status = "REJECTED"
                    await db.commit()

                # Notify the caller
                await call_manager.send_personal_message(
                    {"event_type": "call_reject", "from_user": user_id, "message": "Call rejected."},
                    recipient_id
                )

            elif event_type == "call_end":
                # End an active call
                await call_manager.send_personal_message(
                    {"event_type": "call_end", "from_user": user_id, "message": "Call ended."},
                    recipient_id
                )

            elif event_type == "signal":
                # Exchange signaling data for WebRTC
                await call_manager.send_personal_message(
                    {"event_type": "signal", "from_user": user_id, "payload": payload},
                    recipient_id
                )

            else:
                await websocket.send_json({"error": "Invalid event type."})

    except WebSocketDisconnect:
        await call_manager.disconnect(user_id)
        logger.info(f"User {user_id} disconnected from WebSocket.")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket: {e}")
        await websocket.close(code=1011)  # Close with a server error code

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(rides.router, prefix="/rides", tags=["Rides"])
app.include_router(wallet.router, prefix="/wallet", tags=["Wallet"])
app.include_router(chatMessage.router, prefix="/chatMessage", tags=["ChatMessage"])
app.include_router(pushNotifications.router, prefix="/pushNotifications", tags=["pushNotifications"])
app.include_router(coordinates.router, prefix="/coordinates", tags=["coordinates"])


