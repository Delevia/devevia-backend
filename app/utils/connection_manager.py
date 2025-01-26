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



class CallConnectionManager:
    def __init__(self):
        # Maintain a mapping of user_id to active WebSocket connections
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        """Connect a user to the WebSocket and accept the WebSocket connection."""
        await websocket.accept()
        if user_id in self.active_connections:
            logger.warning(f"User {user_id} already connected. Replacing the existing connection.")
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected.")

    async def disconnect(self, user_id: int):
        """Disconnect a user from the WebSocket and remove them from active connections."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected.")

    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user by their `user_id`."""
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                logger.info(f"Message sent to user {user_id}: {message}")
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                await self.disconnect(user_id)
        else:
            logger.warning(f"User {user_id} not connected. Message not sent: {message}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected users."""
        disconnected_users = []
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect(user_id)
            logger.info(f"User {user_id} removed from active connections due to broadcast failure.")

# Instantiate the CallConnectionManager
manager = CallConnectionManager()