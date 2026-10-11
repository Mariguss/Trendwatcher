import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from sqlalchemy.sql.functions import func

from backend.utils.date import get_now


class CreatedAtMixin:
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=get_now,
        server_default=func.now(),
    )
