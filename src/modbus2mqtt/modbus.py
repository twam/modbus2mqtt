from dataclasses import dataclass
from enum import StrEnum

from construct import Construct


class RegisterType(StrEnum):
    INPUT = "input"
    HOLDING = "holding"


@dataclass(frozen=True)
class RegisterSet:
    address: int
    format: Construct
    register_type: RegisterType = RegisterType.HOLDING
