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

    # title of the document
    title: Mapped[typing.Optional[str]] = mapped_column(
        sqlalchemy.String,
        nullable=True,
        default=None,
        comment="Title of the document"
    )

    # optional author foreign key
    author_id: Mapped[typing.Optional[IDType]] = UUIDFKey(
        ForeignKey("users.id"),
        default=None,
        nullable=True,
        comment="Author (user) of the document"
    )

    # Note: Author relationship is handled via federation in the GraphQL layer
    # since UserModel is defined in another service

    # classification of the document
    classification: Mapped[typing.Optional[str]] = mapped_column(
        sqlalchemy.String,
        nullable=True,
        default="bez klasifikace",
        comment="Classification of the document"
    )

    # language of the document
    language: Mapped[typing.Optional[str]] = mapped_column(
        sqlalchemy.String,
        nullable=True,
        default=None,
        comment="Language of the document (e.g., 'en', 'cs', 'de')"
    )

    # version of the document
    version: Mapped[typing.Optional[str]] = mapped_column(
        sqlalchemy.String,
        nullable=True,
        default="1.0",
        comment="Version identifier of the document"
    )

    # source URL
    source_url: Mapped[typing.Optional[str]] = mapped_column(
        sqlalchemy.String,
        nullable=True,
        default=None,
        comment="Source URL if document came from external source"
    )

    # text to be used for embedding (single large text field)
    content: Mapped[str] = mapped_column(
        sqlalchemy.Text,
        nullable=True,
        default=None,
        comment="Plain text used to compute embeddings"
    )
