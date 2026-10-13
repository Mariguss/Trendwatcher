import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Float,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.models.base import BaseWithId

if TYPE_CHECKING:
    ...


class SourceType(str, enum.Enum):
    RSS = "rss"
    WEB = "web"
    API = "api"


class Source(BaseWithId):
    name: Mapped[str] = mapped_column(String(50))
    source_type: Mapped[SourceType]
    url: Mapped[str] = mapped_column(String(255))
    reliability_score: Mapped[float] = mapped_column(Float)
    api_url: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
