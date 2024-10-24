from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_db
from ..models import ChatMessage, User
from ..utils.connection_manager import ConnectionManager
from sqlalchemy.future import select
from ..utils.connection_manager import manager
from ..utils.chatMessage_schema import ChatMessageResponse
import logging
from typing import Dict




router = APIRouter()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# WebSocket route for riders
@router.websocket("/ws/chat/rider/{ride_id}/{user_id}")
async def rider_chat_websocket(
    websocket: WebSocket, 
    ride_id: int, 
    user_id: int, 
    db: AsyncSession = Depends(get_async_db)
):
    # Accept connection for the rider
    await manager.connect(user_id, websocket)
    
    try:
        while True:
            # Receive messages and process
            data = await websocket.receive_text()
            recipient_id, message = data.split(":", 1)
            
            # Save message to the database
            new_message = ChatMessage(
                ride_id=ride_id,
                sender_id=user_id,
                receiver_id=int(recipient_id),
                message=message,
            )
            db.add(new_message)
            await db.commit()

            # Forward message
            await manager.send_personal_message(message, int(recipient_id))

    except WebSocketDisconnect:
        manager.disconnect(user_id)


# WebSocket route for drivers
@router.websocket("/ws/chat/driver/{ride_id}/{user_id}")
async def driver_chat_websocket(
    websocket: WebSocket, 
    ride_id: int, 
    user_id: int, 
    db: AsyncSession = Depends(get_async_db)
):
    # Accept connection for the driver
    await manager.connect(user_id, websocket)
    
    try:
        while True:
            # Receive messages and process
            data = await websocket.receive_text()
            recipient_id, message = data.split(":", 1)
            
            # Save message to the database
            new_message = ChatMessage(
                ride_id=ride_id,
                sender_id=user_id,
                receiver_id=int(recipient_id),
                message=message,
            )
            db.add(new_message)
            await db.commit()

            # Forward message
            await manager.send_personal_message(message, int(recipient_id))

    except WebSocketDisconnect:
        manager.disconnect(user_id)


# Chat History
@router.get("/chat/history/{ride_id}", response_model=List[ChatMessageResponse])
async def get_chat_history(ride_id: int, user_id: int, db: AsyncSession = Depends(get_async_db)):
    # Fetch the chat messages for a particular ride and user
    result = await db.execute(
        select(ChatMessage).filter((ChatMessage.ride_id == ride_id) & 
                                   ((ChatMessage.sender_id == user_id) | 
                                    (ChatMessage.receiver_id == user_id)))
    )
    messages = result.scalars().all()

    if not messages:
        raise HTTPException(status_code=404, detail="No chat history found for this ride")
    
    return messages




@router.websocket("/ws/test")
async def websocket_endpoint(websocket: WebSocket):
    """Simple WebSocket connection for testing."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Message: {data}")  # Broadcast message to all connected clients
    except WebSocketDisconnect:
        manager.disconnect(websocket)




@router.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        logger.info("Test WebSocket disconnected.")
