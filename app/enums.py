from enum import Enum

class UserType(Enum):
    RIDERS = "RIDERS"
    DRIVERS = "DRIVERS"


class UserStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"