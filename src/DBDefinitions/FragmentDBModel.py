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
from pgvector.sqlalchemy import Vector

###########################################################################################################################
#
# zde definujte sve SQLAlchemy modely
# je-li treba, muzete definovat modely obsahujici jen id polozku, na ktere se budete odkazovat
#
###########################################################################################################################
class FragmentModel(BaseModel):
    __tablename__ = "fragments_evolution"

    path_attribute_name = "path"
    
    # Semantic vector using pgvector - 384 dimensions for all-MiniLM-L6-v2
    vector: Mapped[typing.List[float]] = mapped_column(
        Vector(384),  # all-MiniLM-L6-v2 produces 384-dimensional vectors
        nullable=True,
        default=None,
        comment="Semantic embedding vector for similarity search"
    )

    document_id: Mapped[typing.Optional[IDType]] = mapped_column(
        ForeignKey("documents_evolution.id"),
        default=None,
        nullable=True,
        index=True,
        comment="Document that the fragment originates from."
    )

    # relation to the originating document
    document = relationship(
        "DocumentModel",
        primaryjoin="FragmentModel.document_id==DocumentModel.id",
        uselist=False,
    )

    # text to be used for embedding (single large text field)
    content: Mapped[str] = mapped_column(
        sqlalchemy.Text,
        nullable=True,
        default=None,
        comment="Plain text used to compute embeddings"
    )