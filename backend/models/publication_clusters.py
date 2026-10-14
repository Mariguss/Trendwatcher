import uuid

from sqlalchemy import (
    ForeignKey,
    UUID,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)


from backend.models import RawPublication
from backend.models.base import BaseWithUUID
from backend.models.mixins import CreatedAtMixin

class PublicationCluster(BaseWithUUID, CreatedAtMixin):
    primary_publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rawpublications.id", ondelete="CASCADE"),
        unique=True,
    )

    publication: Mapped[RawPublication] = relationship(
        "RawPublication",
    )
