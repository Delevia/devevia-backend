import requests
from ..utils.sendchamp_http_client import CUSTOM_HTTP_CLIENT

class Email:
    def __init__(self, headers):
        self.headers = headers

    def send_email(self, email_data):
        SENDCHAMP_EMAIL_ENDPOINT = "https://api.sendchamp.com/api/v1/email/send"
        client = CUSTOM_HTTP_CLIENT(SENDCHAMP_EMAIL_ENDPOINT, self.headers)
        response = client.requests("POST", json=email_data)
        return response.json(), response.status_code != 200



class Sendchamp:
    def __init__(self, public_key: str):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {public_key}"
        }
        self.email = Email(headers=self.headers)
