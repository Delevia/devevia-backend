import jwt
from datetime import datetime, timedelta

SECRET_KEY = "edaac9e321d9f0aa975f0929beb0fbed4c0f8e63"  # Replace with your actual secret key
ALGORITHM = "HS256"  # Replace with your actual algorithm

test_payload = {"sub": "1", "exp": datetime.utcnow() + timedelta(days=1)}
test_token = jwt.encode(test_payload, SECRET_KEY, algorithm=ALGORITHM)
print(f"Test token: {test_token}")

decoded_payload = jwt.decode(test_token, SECRET_KEY, algorithms=[ALGORITHM])
print(f"Decoded payload: {decoded_payload}")
