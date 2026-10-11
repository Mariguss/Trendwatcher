import enum
import uuid

from sqlalchemy import (
    ForeignKey,
    String,
    Text, UUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.models.base import BaseWithUUID
from backend.models.mixins import CreatedAtMixin
from backend.models.publication_clusters import PublicationCluster

class Category(str, enum.Enum):
    BANKING_PRODUCT = "BANKING_PRODUCT"
    PAYMENT_SERVICE = "PAYMENT_SERVICE"
    UX_MECHANICS = "UX_MECHANICS"
    PARTNERSHIP = "PARTNERSHIP"
    REGULATION = "REGULATION"
    MARKET = 'MARKET'
    BANK = "BANK"


class Signal(BaseWithUUID, CreatedAtMixin):
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publicationclusters.id", ondelete="CASCADE"),
    )
    category: Mapped[Category]
    headline: Mapped[str] = mapped_column(String(255))
    hotness: Mapped[float]
    why_now: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    draft: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float]

    cluster: Mapped[PublicationCluster] = relationship(
        "PublicationCluster",
    )
