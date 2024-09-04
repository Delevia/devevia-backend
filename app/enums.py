from enum import Enum

class UserType(Enum):
    RIDER = "RIDER"
    DRIVER = "DRIVER"


class UserStatusEnum(str, Enum):
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    AWAITING = "AWAITING"
    DISABLED = "DISABLED"


class PaymentMethodEnum(Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    CASH = "cash"
    WALLET = "wallet"
    PAYPAL = "paypal"  # Example of an additional method


class RideStatusEnum(str, Enum):
    PENDING = "APPROVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"