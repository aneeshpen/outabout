"""Database enums.

These mirror the five PostgreSQL enum types created by the Prisma schema
(``Role``, ``PassType``, ``PassStatus``, ``LogAction``, ``StudentStatus``).
The member *values* are the exact strings stored in the database, which is why
every mapped column below is declared with ``values_callable`` — without it
SQLAlchemy would persist the member *names* instead.
"""

import enum


class Role(str, enum.Enum):
    student = "student"
    warden = "warden"
    guard = "guard"
    admin = "admin"
    other = "other"


class PassType(str, enum.Enum):
    leave = "leave"
    market = "market"
    other = "other"


class PassStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LogAction(str, enum.Enum):
    checked_in = "checked_in"
    checked_out = "checked_out"
    scan = "scan"


class StudentStatus(str, enum.Enum):
    out = "out"
    in_ = "in"
    market = "market"


def enum_values(enum_cls) -> list[str]:
    return [member.value for member in enum_cls]
