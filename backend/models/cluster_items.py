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
from backend.models.publication_clusters import PublicationCluster


class ClusterItem(BaseWithUUID):
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publicationclusters.id", ondelete="CASCADE"),
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rawpublications.id", ondelete="CASCADE"),
    )
    is_primary: Mapped[bool] = mapped_column(default=False, server_default="false")

    cluster: Mapped[PublicationCluster] = relationship(
        "PublicationCluster",
    )
    publication: Mapped[PublicationCluster] = relationship(
        "RawPublication"
    )
