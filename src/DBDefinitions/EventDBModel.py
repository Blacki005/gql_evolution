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

###########################################################################################################################
#
# zde definujte sve SQLAlchemy modely
# je-li treba, muzete definovat modely obsahujici jen id polozku, na ktere se budete odkazovat
#
###########################################################################################################################
class EventModel(BaseModel):
    __tablename__ = "events_evolution"

    path_attribute_name = "path"
    parent_attribute_name = "masterevent"
    parent_id_attribute_name = "masterevent_id"
    children_attribute_name = "subevents"

    # Materialized path technique
    path: Mapped[str] = mapped_column(
        index=True,
        nullable=True,
        default=None,
        comment="Materialized path technique, not implemented"
    )

    name: Mapped[str] = mapped_column(default=None, nullable=True)
    name_en: Mapped[str] = mapped_column(default=None, nullable=True)
    description: Mapped[str] = mapped_column(default=None, nullable=True)
    startdate: Mapped[datetime.datetime] = mapped_column(default=None, nullable=True)
    enddate: Mapped[datetime.datetime] = mapped_column(default=None, nullable=True)
    
    place: Mapped[str] = mapped_column(default=None, nullable=True)
    facility_id: Mapped[IDType] = UUIDFKey(nullable=True)

    @hybrid_property
    def duration(self):
        return self.enddate - self.startdate

    @hybrid_property
    def valid(self):
        """Evaluates if the entity is valid based on the current datetime."""
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.startdate and self.enddate:
            return self.startdate <= now <= self.enddate
        elif self.startdate:
            return self.startdate <= now
        elif self.enddate:
            return now <= self.enddate
        return False

    @valid.expression
    def valid(cls):
        """Defines the SQL expression for the 'valid' property."""
        now = datetime.datetime.utcnow()
        return sqlalchemy.and_(
            sqlalchemy.or_(cls.startdate <= now, cls.startdate.is_(None)),  # Valid if startdate is in the past or missing
            sqlalchemy.or_(cls.enddate >= now, cls.enddate.is_(None))       # Valid if enddate is in the future or missing
        )


    # the real column in the DB
    masterevent_id: Mapped[IDType] = mapped_column(
        ForeignKey("events_evolution.id"),
        nullable=True,
        default=None,
        index=True,
    )


    masterevent = relationship(
        "EventModel",
        viewonly=True, 
        remote_side="EventModel.id",
        uselist=False,
        back_populates="subevents",
    ) # https://docs.sqlalchemy.org/en/20/orm/self_referential.html

    subevents = relationship(
        "EventModel", 
        back_populates="masterevent",
        uselist=True,
        init=True,
        cascade="save-update"
    ) # https://docs.sqlalchemy.org/en/20/orm/self_referential.html
    # https://docs.sqlalchemy.org/en/20/_modules/examples/materialized_paths/materialized_paths.html

    user_invitations = relationship(
        "EventInvitationModel",
        uselist=True,
        init=True,
        cascade="save-update"
    )