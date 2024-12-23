from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

# Database URL
DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost/delevia_db"

# Set up the async engine with optional echo for debugging
async_engine = create_async_engine(DATABASE_URL, future=True, echo=True)

# Create a sessionmaker for the async session
async_session = sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Base model for declarative class definitions
Base = declarative_base()

# Get the async database session
async def get_async_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
