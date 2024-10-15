from enum import Enum

class UserType(str, Enum):
    RIDER = "RIDER"
    DRIVER = "DRIVER"


class UserStatusEnum(str, Enum):
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    AWAITING = "AWAITING"
    DISABLED = "DISABLED"


class PaymentMethodEnum(str, Enum):
    DEBIT_CARD = "debit_card"
    CASH = "cash"
    WALLET = "wallet"


class RideStatusEnum(str, Enum):
    INITIATED = 'INITIATED'
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"


class RideTypeEnum(str, Enum):
    STANDARD = "STANDARD "
    VIP = "VIP"


class RidePaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"


class WalletTransactionEnum(str, Enum):
    CREDIT = 'CREDIT'
    DEBIT = 'DEBIT' 

