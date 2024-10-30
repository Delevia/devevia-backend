from fastapi import WebSocket
from typing import List
from typing import Dict  # Import Dict from typing
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



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