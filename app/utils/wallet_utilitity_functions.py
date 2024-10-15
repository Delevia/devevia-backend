import random



def generate_account_number() -> str:
    """Generates a 10-digit random account number."""
    return str(random.randint(1000000000, 9999999999))
