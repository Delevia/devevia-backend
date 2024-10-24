from fastapi import WebSocket
from typing import List
from typing import Dict  # Import Dict from typing
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Connection Manager to keep track of connected clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}  # Store WebSocket connections by user_id

    async def connect(self, user_id: int, websocket: WebSocket):
        """Connect a user and accept the WebSocket connection."""
        try:
            await websocket.accept()
            self.active_connections[user_id] = websocket  # Map user_id to the WebSocket connection
            logger.info(f"User {user_id} connected and WebSocket accepted.")
        except Exception as e:
            logger.error(f"Error during WebSocket acceptance for user {user_id}: {e}")
            raise

    def disconnect(self, user_id: int):
        """Disconnect a user by removing their WebSocket connection."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]  # Remove the WebSocket connection for the user
            logger.info(f"User {user_id} WebSocket disconnected.")

    async def send_personal_message(self, message: str, recipient_id: int):
        """Send a personal message to a specific user identified by recipient_id."""
        if recipient_id in self.active_connections:
            websocket = self.active_connections[recipient_id]  # Get the recipient's WebSocket
            try:
                await websocket.send_text(message)  # Send the message to the recipient
                logger.info(f"Message sent to user {recipient_id}: {message}")
            except Exception as e:
                logger.error(f"Error sending message to user {recipient_id}: {e}")
                raise

# Instantiate the manager
manager = ConnectionManager()