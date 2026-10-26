"""Timezone helpers.

The database stores naive ``TIMESTAMP`` values in UTC (that is what
``CURRENT_TIMESTAMP`` produces on the managed PostgreSQL instance, and what
Prisma handed to the old Express responses).  Two things depend on that:

* API responses must say so explicitly, otherwise a browser parsing
  ``2026-10-25T16:05:00`` would treat it as *local* time and render gate scan
  times hours off.  :func:`as_utc` attaches ``tzinfo`` before serialisation.
* The "late return" rule is expressed in Indian Standard Time, so
  :func:`to_ist` converts before the hour is compared.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))
LATE_RETURN_HOUR_IST = 21  # 9 PM


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Interpret a naive datetime as UTC; leave aware datetimes alone."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def to_ist(value: Optional[datetime]) -> Optional[datetime]:
    aware = as_utc(value)
    return None if aware is None else aware.astimezone(IST)


def ist_today():
    """Today's date in IST - the campus' own notion of "today"."""
    return datetime.now(IST).date()
