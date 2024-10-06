# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    
    class Config:
        env_file = ".env"  # Specifies the .env file to load settings from
        extra = "allow"  # This allows extra fields


settings = Settings()


