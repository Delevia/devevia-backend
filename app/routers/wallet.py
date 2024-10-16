from fastapi import APIRouter, HTTPException, status, Depends
from ..database import get_async_db  # Ensure to update this to get the async session
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Wallet, Transaction
from ..utils.wallet_schema import  WalletResponse, TransactionCreate, TransactionResponse, TransactionHistoryResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# Get the wallet balance for a user
@router.get("/wallets/{user_id}", response_model=WalletResponse)
async def get_wallet_balance(user_id: int, db: AsyncSession = Depends(get_async_db)):
    # Query the wallet by user ID
    result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id))
    wallet = result.scalars().first()

    # Raise error if wallet not found
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return wallet

# Add funds (credit) to the wallet
@router.post("/wallets/credit/", response_model=TransactionResponse)
async def credit_wallet(account_number: str, transaction: TransactionCreate, db: AsyncSession = Depends(get_async_db)):
    # Find the wallet by the account number using select
    query = select(Wallet).filter(Wallet.account_number == account_number)
    result = await db.execute(query)  # Execute the query asynchronously
    wallet = result.scalars().first()  # Get the first result

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if transaction.transaction_type != "CREDIT":
        raise HTTPException(status_code=400, detail="Transaction type must be CREDIT to add funds")

    # Add the amount to the wallet balance
    wallet.balance += transaction.amount
    db.add(wallet)  # Mark wallet for updating
    
    # Record the transaction
    new_transaction = Transaction(wallet_id=wallet.id, amount=transaction.amount, transaction_type=transaction.transaction_type)
    db.add(new_transaction)  # Mark transaction for adding
    await db.commit()  # Commit the changes asynchronously
    await db.refresh(new_transaction)  # Refresh the transaction to get updated data
    
    # Prepare the response including the account number
    response = TransactionResponse(
        amount=new_transaction.amount,
        transaction_type=new_transaction.transaction_type,
        created_at=new_transaction.created_at,
        account_number=wallet.account_number  # Include account number from wallet
    )
    
    return response  # Return the response with account number


# Deduct funds (debit) from the wallet
@router.post("/wallets/{account_number}/deduct_funds", response_model=TransactionResponse)
async def deduct_funds(account_number: str, transaction: TransactionCreate, db: AsyncSession = Depends(get_async_db)):
    # Query the wallet by account number
    result = await db.execute(select(Wallet).filter(Wallet.account_number == account_number))
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Check if the transaction type is DEBIT
    if transaction.transaction_type != "DEBIT":
        raise HTTPException(status_code=400, detail="Transaction type must be DEBIT to deduct funds")
    
    # Check if the wallet has sufficient balance
    if wallet.balance < transaction.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Deduct the amount from the wallet balance
    wallet.balance -= transaction.amount
    db.add(wallet)
    
    # Record the transaction
    new_transaction = Transaction(
        wallet_id=wallet.id, 
        amount=transaction.amount, 
        transaction_type=transaction.transaction_type
    )
    db.add(new_transaction)
    await db.commit()
    await db.refresh(new_transaction)
    
    # Manually include account_number in the response
    response = TransactionResponse(
        id=new_transaction.id,
        amount=new_transaction.amount,
        transaction_type=new_transaction.transaction_type,
        created_at=new_transaction.created_at,
        account_number=wallet.account_number  # Include account number from wallet
    )
    
    return response


# Get the wallet transaction history for a wallet (by account number)
@router.get("/wallets/{account_number}/history", response_model=list[TransactionHistoryResponse])
async def get_wallet_history(user_id: int, db: AsyncSession = Depends(get_async_db)):
    # Query the wallet by account number
    result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id ))
    wallet = result.scalars().first()

    # Raise error if wallet not found
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Fetch all transactions related to this wallet
    transactions_result = await db.execute(select(Transaction).filter(Transaction.wallet_id == wallet.id))
    transactions = transactions_result.scalars().all()

    # If no transactions found, raise a 404 error
    if not transactions:
        raise HTTPException(status_code=404, detail="No transaction history found for this wallet")

    return transactions