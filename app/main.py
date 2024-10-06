from fastapi import FastAPI
from .routers import auth, users, rides
from .database import Base, async_engine  # Import async_engine from your database module
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

# Initialize FastAPI app
app = FastAPI()

# Asynchronous function to create tables
async def create_tables():
    async with async_engine.begin() as conn:
        # Create all the tables in the database asynchronously
        await conn.run_sync(Base.metadata.create_all)

# Run the table creation when the app starts
@app.on_event("startup")
async def on_startup():
    await create_tables()

# Include routers (ensure they are asynchronous as well)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(rides.router, prefix="/rides", tags=["Rides"])

# You can also add other global settings, middleware, etc., here if needed.
