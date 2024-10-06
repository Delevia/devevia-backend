

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from ..models import RefreshToken, BlacklistedToken
from ..database import get_async_db
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Configuration variables
SECRET_KEY = "edaac9e321d9f0aa975f0929beb0fbed4c0f8e63"  # Replace with a secure key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Access token expiry time
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Refresh token expiry time

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



# Create Access Token
def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=15)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "sub": str(data["sub"])})  # Convert sub to string
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



# Create Refresh Token
def create_refresh_token(data: dict, db: Session, expires_delta: timedelta = timedelta(days=7)) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "sub": str(data["sub"])})  # Convert sub to string
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    try:
        # Create a new RefreshToken record
        refresh_token = RefreshToken(
            token=encoded_jwt,
            user_id=int(data["sub"]),  # Convert back to integer for database storage
            expires_at=expire
        )
        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)
    except SQLAlchemyError as e:
        # Handle any database errors
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    return encoded_jwt



def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)



# Decode Refresh Token
def decode_refresh_token(token: str, db: Session) -> dict:
    """Decode a refresh token and validate it."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Decoded payload: {payload}")  # Debugging line
        user_id = str(payload.get("sub"))  # Ensure user_id is treated as a string
        print(f"User ID from payload: {user_id}")  # Debugging line
        if user_id is None:
            print("No user_id found in payload")  # Debugging line
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Convert user_id back to integer for querying the database
        refresh_token_record = db.query(RefreshToken).filter(
            RefreshToken.token == token,
            RefreshToken.user_id == int(user_id),  # Convert to integer for querying
            RefreshToken.expires_at > datetime.utcnow()
        ).first()

        if not refresh_token_record:
            print("Refresh token record not found or expired")  # Debugging line
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    except JWTError as e:
        print(f"JWTError: {e}")  # Debugging line
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )



def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


# Check if the given access token is in the blacklist
def is_token_blacklisted(token: str, db: Session) -> bool:
    """Check if the given access token is in the blacklist."""
    return db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first() is not None


# Decode an access token
def decode_access_token(token: str, db: Session) -> dict:
    """Decode an access token and validate it."""
    if is_token_blacklisted(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )



