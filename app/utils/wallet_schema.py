from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Response model to return wallet details
class WalletResponse(BaseModel):
    user_id: int
    balance: float
    account_number: str

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    amount: float
    transaction_type: str  # Should be either 'CREDIT' or 'DEBIT'

class TransactionResponse(BaseModel):
    amount: float
    transaction_type: str
    account_number: str  
    created_at: datetime

    class Config:
        from_attributes = True


# Response model for transaction details
class TransactionHistoryResponse(BaseModel):
    id: int
    amount: float
    transaction_type: str
    created_at: datetime

    class Config:
        from_attributes = True