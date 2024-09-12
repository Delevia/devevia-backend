# app/main.py
from fastapi import FastAPI
from .routers import auth, users
from .database import Base, engine  # Import Base and engine from your database module

# Create all the tables in the database
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI()

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])

# Other global settings, middleware, etc.
