# dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Optional
from ..import models
from ..database import get_async_db
import hashlib
import uuid



# Secret key for JWT token validation
SECRET_KEY = "edaac9e321d9f0aa975f0929beb0fbed4c0f8e63"
  # Should be stored in config or environment
ALGORITHM = "HS256"  # The algorithm for JWT encryption
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_async_db)) -> models.User:
    """Extract and verify the JWT token, and return the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        # Fetch user from the database
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if user is None:
            raise credentials_exception
    
    except JWTError:
        raise credentials_exception

    return user




def generate_hashed_referral_code():
    new_uuid = uuid.uuid4()
    # Create a hash from the UUID
    hash_object = hashlib.sha256(new_uuid.bytes)
    # Get the first 8 characters of the hex digest
    return hash_object.hexdigest()[:10]