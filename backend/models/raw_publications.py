import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.models.base import BaseWithUUID
from backend.models.sources import Source


class RawPublication(BaseWithUUID):
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"),
    )
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(255), unique=True)
    embedded: Mapped[list[float] | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    source: Mapped[Source] = relationship(
        "Source",
    )
