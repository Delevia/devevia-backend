from fastapi import FastAPI
from app.routers import auth, users, rides, wallet, chatMessage
from app.database import Base, async_engine  # Import async_engine from your database module
from fastapi.middleware.cors import CORSMiddleware
from app.models import  Ride
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_db
from app.models import ChatMessage
from app.utils.connection_manager import ConnectionManager
from sqlalchemy.future import select
from app.utils.connection_manager import manager
import logging
from typing import Dict



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



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)





router = APIRouter()


# Asynchronous function to create tables
async def create_tables():
    async with async_engine.begin() as conn:
        # Create all the tables in the database asynchronously
        await conn.run_sync(Base.metadata.create_all)

# Run the table creation when the app starts
@app.on_event("startup")
async def on_startup():
    await create_tables()


from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


# Revised Connection Manager to handle single connection per user
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}  # Store one WebSocket connection per user_id

    async def connect(self, user_id: int, websocket: WebSocket):
        """Connect a user and accept the WebSocket connection. If a connection already exists, disconnect the old one."""
        # Disconnect existing connection if the user is already connected
        if user_id in self.active_connections:
            existing_socket = self.active_connections[user_id]
            try:
                await existing_socket.close()  # Close the previous WebSocket connection
                logger.info(f"Closed previous connection for user {user_id}.")
            except Exception as e:
                logger.error(f"Error closing WebSocket for user {user_id}: {e}")
        
        # Accept the new connection
        try:
            await websocket.accept()
            self.active_connections[user_id] = websocket  # Store the new WebSocket connection
            logger.info(f"User {user_id} connected with a new WebSocket.")
        except Exception as e:
            logger.error(f"Error during WebSocket acceptance for user {user_id}: {e}")
            raise

    async def disconnect(self, user_id: int):
        """Disconnect a user by removing their WebSocket connection."""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.close()  # Close the WebSocket connection
                logger.info(f"User {user_id} WebSocket disconnected.")
            except Exception as e:
                logger.error(f"Error closing WebSocket for user {user_id}: {e}")
            finally:
                del self.active_connections[user_id]  # Remove the WebSocket connection for the user

    async def send_personal_message(self, message: str, recipient_id: int):
        """Send a personal message to a specific user identified by recipient_id."""
        if recipient_id in self.active_connections:
            websocket = self.active_connections[recipient_id]  # Get the recipient's WebSocket
            try:
                await websocket.send_text(message)  # Send the message to the recipient
                logger.info(f"Message sent to user {recipient_id}: {message}")
            except Exception as e:
                logger.error(f"Error sending message to user {recipient_id}: {e}")
                await self.disconnect(recipient_id)  # Disconnect on error

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
                logger.info(f"Broadcast message to user {user_id}: {message}")
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                await self.disconnect(user_id)  # Disconnect on error

# Instantiate the manager
manager = ConnectionManager()

@app.websocket("/ws/chat/{ride_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, ride_id: int, user_id: int, db: AsyncSession = Depends(get_async_db)):
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

    except WebSocketDisconnect:
        await manager.disconnect(user_id)
        logger.info(f"User {user_id} disconnected from WebSocket.")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket: {e}")
        await websocket.close(code=1011)  # Close with a server error code


# Include routers (ensure they are asynchronous as well)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(rides.router, prefix="/rides", tags=["Rides"])
app.include_router(wallet.router, prefix="/wallet", tags=["Wallet"])
app.include_router(chatMessage.router, prefix="/chatMessage", tags=["chatMessage"])



