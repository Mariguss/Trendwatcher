from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.models.base import BaseWithId

if TYPE_CHECKING:
    ...


class TargetRole(BaseWithId):
    name: Mapped[str] = mapped_column(String(50))
