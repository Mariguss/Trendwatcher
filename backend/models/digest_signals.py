import uuid

from sqlalchemy import (
    ForeignKey, UUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.models.base import BaseWithUUID
from backend.models.digests import Digest
from backend.models.signals import Signal


class DigestSignal(BaseWithUUID):
    digest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="CASCADE"),
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signals.id", ondelete="CASCADE"),
    )

    signal: Mapped[Signal] = relationship(
        "Signal",
    )
    digest: Mapped[Digest] = relationship(
        "Digest",
    )
