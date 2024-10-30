import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .. models import Wallet, CompanyWallet

async def generate_global_unique_account_number(db: AsyncSession):
    while True:
        # Generate a random 10-digit account number
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(10)])

        # Check for uniqueness in both Wallet and CompanyWallet tables
        wallet_exists = (await db.execute(
            select(Wallet).where(Wallet.account_number == account_number)
        )).scalars().first()

        company_wallet_exists = (await db.execute(
            select(CompanyWallet).where(CompanyWallet.account_number == account_number)
        )).scalars().first()

        if not wallet_exists and not company_wallet_exists:
            return account_number
