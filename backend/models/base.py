from pgvector.sqlalchemy import Vector
from sqlalchemy import MetaData
from sqlalchemy.orm import (
    DeclarativeBase,
    declared_attr,
)

from backend.core.config import settings
from backend.models.mixins import IntIdPKMixin


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls):
        return f"{cls.__name__.lower()}s"

    type_annotation_map = {
        list[float]: Vector(312),
    }

    metadata = MetaData(
        naming_convention=settings.db.naming_convention,
    )


class BaseWithId(Base, IntIdPKMixin):
    __abstract__ = True


class BaseWithUUID(Base, IntIdPKMixin):
    __abstract__ = True
