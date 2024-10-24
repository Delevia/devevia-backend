from pydantic import BaseModel
from typing import List

class ChatMessageResponse(BaseModel):
    sender_id: int
    receiver_id: int
    content: str
    timestamp: str  # or datetime if you handle it correctly

    class Config:
        orm_mode = True  # Allows parsing from ORM objects (SQLAlchemy)


# Request schema (used when sending a message)
class SendMessageRequest(BaseModel):
    content: str