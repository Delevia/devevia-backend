from fastapi import APIRouter, HTTPException, status, Depends
from ..database import get_async_db  # Ensure to update this to get the async session
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Wallet, Transaction, CompanyWallet
from ..utils.wallet_schema import  WalletResponse, TransactionCreate, TransactionResponse, TransactionHistoryResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..utils.wallet_utilitity_functions import generate_global_unique_account_number
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


# Create Company Wallet endpoint
@router.post("/company-wallet/create", status_code=status.HTTP_201_CREATED)
async def create_company_wallet(db: AsyncSession = Depends(get_async_db)):
    try:
        # Check if a company wallet already exists
        existing_wallet_query = select(CompanyWallet)
        existing_wallet = (await db.execute(existing_wallet_query)).scalars().first()
        
        if existing_wallet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company wallet already exists"
            )

        # Generate a unique account number for the company wallet
        account_number = await generate_global_unique_account_number(db)

        # Create the new company wallet with the generated account number
        new_wallet = CompanyWallet(balance=0.0, account_number=account_number)
        db.add(new_wallet)
        await db.commit()
        await db.refresh(new_wallet)

        return {
            "message": "Company wallet created successfully",
            "wallet_id": new_wallet.id,
            "account_number": new_wallet.account_number,
            "balance": new_wallet.balance
        }
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )    
    
# Endpoint to check for company account number
@router.get("/company-wallet/account-number", status_code=status.HTTP_200_OK)
async def get_company_account_number(db: AsyncSession = Depends(get_async_db)):
    try:
        # Query to get the company wallet
        wallet_query = select(CompanyWallet)
        wallet = (await db.execute(wallet_query)).scalars().first()
        
        # Check if the company wallet exists
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company wallet not found"
            )

        # Return the account number if wallet exists
        return {
            "account_number": wallet.account_number
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}"
        )
    