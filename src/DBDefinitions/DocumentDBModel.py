import typing
import datetime
import dataclasses
import sqlalchemy
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, synonym

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, column_property

from .BaseModel import BaseModel, UUIDColumn, UUIDFKey, IDType
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID

###########################################################################################################################
#
# zde definujte sve SQLAlchemy modely
# je-li treba, muzete definovat modely obsahujici jen id polozku, na ktere se budete odkazovat
#
###########################################################################################################################
class DocumentModel(BaseModel):
    __tablename__ = "documents_evolution"

    path_attribute_name = "path"

    fragments = relationship(
        "FragmentModel",
        uselist=True,
        init=True,
        cascade="save-update",
        overlaps="document"
    )  # assumes FragmentModel has document_id FK

    # text to be used for embedding (single large text field)
    content: Mapped[str] = mapped_column(
        sqlalchemy.Text,
        nullable=True,
        default=None,
        comment="Plain text used to compute embeddings"
    )
