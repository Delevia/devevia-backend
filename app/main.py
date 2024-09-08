from fastapi import FastAPI
from .routers import auth, users

app = FastAPI()

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])

# Other global settings, middleware, etc.
