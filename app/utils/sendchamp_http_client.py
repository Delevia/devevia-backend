import httpx
from .sendchamp_errors import Error

class CUSTOM_HTTP_CLIENT:

    def __init__(self, url, headers):
        self.url = url
        self.headers = headers
    
    def __call__(self, method, data=None):
        method = method.upper()
        if method not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            raise NotImplementedError(f"Method '{method}' not recognized.")

        # Map method names to httpx methods
        method_map = {
            "GET": httpx.get,
            "POST": httpx.post,
            "PUT": httpx.put,
            "PATCH": httpx.patch,
            "DELETE": httpx.delete
        }

        make_request = method_map[method]

        # Making the request
        if method in ["GET", "DELETE"]:
            res = make_request(self.url, headers=self.headers)
        else:
            res = make_request(self.url, json=data, headers=self.headers)

        # Check for response status
        try:
            json_response = res.json()
            data = json_response.get("data")
            error = Error(**json_response) if "error" in json_response else None

            return data, error

        except Exception as e:
            raise Exception(f"An error occurred while processing the response: {e}")

    def use_url(self, url):
        return CUSTOM_HTTP_CLIENT(url=url, headers=self.headers)
