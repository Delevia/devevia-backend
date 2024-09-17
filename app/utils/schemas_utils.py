from pydantic import BaseModel, Field

class OtpPhoneNumberRequest(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=15,
        pattern="^[0-9]+$"  # Use `pattern` instead of `regex`
    )
