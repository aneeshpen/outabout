"""Shared schema building blocks."""

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, PlainSerializer

from app.utils.timezone import as_utc

# A datetime that always serialises with an explicit UTC offset, matching the
# ISO strings the Express/Prisma backend produced.
UTCDateTime = Annotated[
    datetime,
    PlainSerializer(
        lambda value: as_utc(value).isoformat().replace("+00:00", "Z"),
        return_type=str,
        when_used="json",
    ),
]

OptionalUTCDateTime = Optional[UTCDateTime]


class ORMModel(BaseModel):
    """Base for every response schema that is built from an ORM row."""

    model_config = ConfigDict(from_attributes=True)
