import asyncio
import dataclasses
import datetime
import typing
import strawberry

import strawberry.types
from uoishelpers.gqlpermissions import (
    OnlyForAuthentized,
    SimpleInsertPermission, 
    SimpleUpdatePermission, 
    SimpleDeletePermission
)    
from uoishelpers.resolvers import (
    getLoadersFromInfo, 
    createInputs,
    createInputs2,

    InsertError, 
    Insert, 
    UpdateError, 
    Update, 
    DeleteError, 
    Delete,

    PageResolver,
    VectorResolver,
    ScalarResolver
)
from uoishelpers.gqlpermissions.LoadDataExtension import LoadDataExtension
from uoishelpers.gqlpermissions.RbacProviderExtension import RbacProviderExtension
from uoishelpers.gqlpermissions.RbacInsertProviderExtension import RbacInsertProviderExtension
from uoishelpers.gqlpermissions.UserRoleProviderExtension import UserRoleProviderExtension
from uoishelpers.gqlpermissions.UserAccessControlExtension import UserAccessControlExtension
from uoishelpers.gqlpermissions.UserAbsoluteAccessControlExtension import UserAbsoluteAccessControlExtension

from .BaseGQLModel import BaseGQLModel, IDType, Relation
from .TimeUnit import TimeUnit

EventInvitationGQLModel = typing.Annotated["EventInvitationGQLModel", strawberry.lazy(".EventInvitationGQLModel")]
EventInvitationInputFilter = typing.Annotated["EventInvitationInputFilter", strawberry.lazy(".EventInvitationGQLModel")]

@createInputs2
class EventInputFilter:
    name: str
    name_en: str
    description: str
    startdate: datetime.datetime
    enddate: datetime.datetime
    id: IDType
    valid: bool
    user_invitations: EventInvitationInputFilter = strawberry.field(description="""Eventinvitation filter operators, 
for field "user_invitations" the filters could be
{"user_invitations": {"user_id": {"_eq": "ce22d5ab-f867-4cf1-8e3c-ee77eab81c24"}}}
{"user_invitations": {"state_id": {"_eq": "91fcbf2d-8acd-49ac-ac7e-39c3e23e2ea1"}}}
{"user_invitations": {"_and": [{"user_id": {"_eq": "ce22d5ab-f867-4cf1-8e3c-ee77eab81c24"}}, {"state_id": {"_eq": "91fcbf2d-8acd-49ac-ac7e-39c3e23e2ea1"}}]}}
""")

@strawberry.federation.type(
    description="""Entity representing a Event""",
    keys=["id"]
)
class EventGQLModel(BaseGQLModel):
    @classmethod
    def getLoader(cls, info: strawberry.types.Info):
        return getLoadersFromInfo(info).EventModel

    path: typing.Optional[str] = strawberry.field(
        description="""Materialized path representing the group's hierarchical location.  
Materializovaná cesta reprezentující umístění skupiny v hierarchii.""",
        default=None,
        permission_classes=[OnlyForAuthentized]
    )

    name: typing.Optional[str] = strawberry.field(
        default=None,
        description="""Event name assigned by an administrator""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    name_en: typing.Optional[str] = strawberry.field(
        default=None,
        description="""Event eng name assigned by an administrator""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    description: typing.Optional[str] = strawberry.field(
        default=None,
        description="""Event description""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    startdate: typing.Optional[datetime.datetime] = strawberry.field(
        default=None,
        description="""Event start date""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    enddate: typing.Optional[datetime.datetime] = strawberry.field(
        default=None,
        description="""Event end date""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    # duration: strawberry.Private[object] = None
    duration: typing.Optional[datetime.timedelta] = strawberry.field(
        name="duration_raw",
        default=None,
        description="""len""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    valid: typing.Optional[bool] = strawberry.field(
        name="valid_raw",
        description="""If it intersects current date""",
        default=None,
        permission_classes=[OnlyForAuthentized]
    )

    @strawberry.field(
        name="valid",
        description="""Event duration, implicitly in minutes""",
        permission_classes=[
            OnlyForAuthentized,
            # OnlyForAdmins
        ],
    )
    def valid_(self) -> typing.Optional[bool]:
        if self.valid is not None:
            return self.valid
        now = datetime.datetime.now()
        if self.startdate and self.enddate:
            return self.startdate <= now <= self.enddate
        elif self.startdate:
            return self.startdate <= now
        elif self.enddate:
            return now <= self.enddate
        return False

    @strawberry.field(
        name="duration",
        description="""Event duration, implicitly in minutes""",
        permission_classes=[
            # OnlyForAuthentized,
            # OnlyForAdmins
        ],
    )
    def _duration(self, unit: TimeUnit=TimeUnit.MINUTES) -> typing.Optional[float]:
        duration = self.duration
        if duration is None:
            if self.startdate is None or self.enddate is None:
                return None
            duration = (self.enddate - self.startdate)
        result = duration.total_seconds()
        if unit == TimeUnit.SECONDS:
            return result
        if unit == TimeUnit.MINUTES:
            return result / 60
        if unit == TimeUnit.HOURS:
            return result / 60 / 60
        if unit == TimeUnit.DAYS:
            return result / 60 / 60 / 24
        if unit == TimeUnit.WEEKS:
            return result / 60 / 60 / 24 / 7
        # raise Exception("Unknown unit for duration")


    place: typing.Optional[str] = strawberry.field(
        default=None,
        description="where the event will happen",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    facility_id: typing.Optional[IDType] = strawberry.field(
        default=None,
        description="place where the event will happen, defined by id",
        permission_classes=[
            OnlyForAuthentized
        ],
        directives=[Relation(to="FacilityGQLModel")]
    )

    masterevent_id: typing.Optional[IDType] = strawberry.field(
        default=None,
        description="""Event parent id""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )
    
    masterevent: typing.Optional["EventGQLModel"] = strawberry.field(
        description="""Event which owns this particular event""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=ScalarResolver["EventGQLModel"](fkey_field_name="masterevent_id")
    )

    subevents: typing.List["EventGQLModel"] = strawberry.field(
        description="""Event children""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=VectorResolver["EventGQLModel"](fkey_field_name="masterevent_id", whereType=EventInputFilter)
    )

    user_invitations: typing.List["EventInvitationGQLModel"] = strawberry.field(
        description="""Event invitations""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=VectorResolver["EventInvitationGQLModel"](fkey_field_name="event_id", whereType=EventInvitationInputFilter)
    )



@strawberry.interface(
    description="""Event queries"""
)
class EventQuery:
    event_by_id: typing.Optional[EventGQLModel] = strawberry.field(
        description="""get a event by its id""",
        permission_classes=[OnlyForAuthentized],
        resolver=EventGQLModel.load_with_loader
    )

    event_page: typing.List[EventGQLModel] = strawberry.field(
        description="""get a page of events""",
        permission_classes=[OnlyForAuthentized],
        resolver=PageResolver[EventGQLModel](whereType=EventInputFilter)
    )

from uoishelpers.resolvers import TreeInputStructureMixin, InputModelMixin
@strawberry.input(
    description="""Input type for creating a Event"""
)
class EventInsertGQLModel(TreeInputStructureMixin):
    getLoader = EventGQLModel.getLoader
    masterevent_id: IDType = strawberry.field(
        description="""Event parent id""",
        # default=None
    )
    name: typing.Optional[str] = strawberry.field(
        description="""Event name assigned by an administrator""",
        default=None
    )
    name_en: typing.Optional[str] = strawberry.field(
        description="""Event eng name assigned by an administrator""",
        default=None
    )
    description: typing.Optional[str] = strawberry.field(
        description="""Event description""",
        default=None
    )
    start_date: typing.Optional[datetime.datetime] = strawberry.field(
        description="""Event start date""",
        default=None
    )
    end_date: typing.Optional[datetime.datetime] = strawberry.field(
        description="""Event end date""",
        default=None
    )
    id: typing.Optional[IDType] = strawberry.field(
        description="""Event id""",
        default=None
    )
    subevents: typing.Optional[typing.List["EventInsertGQLModel"]] = strawberry.field(
        description="sub events",
        default_factory=list
    )

    rbacobject_id: strawberry.Private[IDType] = None
    createdby_id: strawberry.Private[IDType] = None


@strawberry.input(
    description="""Input type for creating a Plan"""
)
class EventPlanInsertGQLModel(TreeInputStructureMixin):
    getLoader = EventGQLModel.getLoader
    rbacobject_id: IDType = strawberry.field(
        description="""id of the group the plan is for""",
        # default=None
    )
    name: typing.Optional[str] = strawberry.field(
        description="""Event name assigned by an administrator""",
        default=None
    )
    name_en: typing.Optional[str] = strawberry.field(
        description="""Event eng name assigned by an administrator""",
        default=None
    )
    description: typing.Optional[str] = strawberry.field(
        description="""Event description""",
        default=None
    )
    start_date: typing.Optional[datetime.datetime] = strawberry.field(
        description="""Plan start date""",
        default=None
    )
    end_date: typing.Optional[datetime.datetime] = strawberry.field(
        description="""Plan end date""",
        default=None
    )
    masterevent_id: typing.Optional[IDType] = strawberry.field(
        description="""Plan parent id""",
        default=None
    )
    id: typing.Optional[IDType] = strawberry.field(
        description="""Event id""",
        default=None
    )
    subevents: typing.Optional[typing.List["EventInsertGQLModel"]] = strawberry.field(
        description="sub events",
        default_factory=list
    )

    
    createdby_id: strawberry.Private[IDType] = None

@strawberry.input(
    description="Invitation model"
)
class EventInvitationInsertModel(InputModelMixin):
    @staticmethod
    def getLoader(info):
        return getLoadersFromInfo(info).EventInvitationModel
    
    id: typing.Optional[IDType] = strawberry.field(
        description="""Event id""",
        default=None
    )
    user_id: IDType = strawberry.field(
        description="""invited user""",
    )
    state_id: IDType = strawberry.field(
        description="""invitation state""",
    )
    event_id: typing.Optional[IDType] = strawberry.field(
        description="""event inviting to""",
    )
    createdby_id: strawberry.Private[IDType]
    
@strawberry.input(
    description="Model for batch invitation to the event"
)
class EventEnsureUserInvitationsModel:
    getLoader = EventGQLModel.getLoader
    id: IDType = strawberry.field(
        description="""Event id""",
        # default=None
    )
    user_invitations: typing.Optional[typing.List[EventInvitationInsertModel]] = strawberry.field(
        description="",
        default_factory=list
    )
    
    pass

@strawberry.input(
    description=""
)
class EventReservationInsertModel(InputModelMixin):
    @staticmethod
    def getLoader(info):
        return getLoadersFromInfo(info).EventFacilityReservationModel
    
    facility_id: IDType = strawberry.field(
        description="""reserved facility""",
    )
    state_id: IDType = strawberry.field(
        description="""reservation state""",
    )
    event_id: typing.Optional[IDType] = strawberry.field(
        description="""event related to facility reservation""",
    )
    id: typing.Optional[IDType] = strawberry.field(
        description="""Event id""",
        default=None
    )
    createdby_id: strawberry.Private[IDType]

@strawberry.input(
    description=""
)
class EventEnsureFacilityReservationsModel():
    getLoader = EventGQLModel.getLoader
    id: typing.Optional[IDType] = strawberry.field(
        description="""Event id""",
        default=None
    )
    facility_reservations: typing.Optional[typing.List[EventReservationInsertModel]] = strawberry.field(
        description="",
        default_factory=list
    )
    pass

@strawberry.input(
    description="""Input type for updating a Event"""
)
class EventUpdateGQLModel:
    id: IDType = strawberry.field(
        description="""Event id""",
    )
    lastchange: datetime.datetime = strawberry.field(
        description="timestamp"
    )
    name: typing.Optional[str] = strawberry.field(
        description="""Event name assigned by an administrator""",
        default=None
    )
    name_en: typing.Optional[str] = strawberry.field(
        description="""Event eng name assigned by an administrator""",
        default=None
    )
    description: typing.Optional[str] = strawberry.field(
        description="""Event description""",
        default=None
    )
    startdate: typing.Optional[datetime.datetime] = strawberry.field(
        description="""Event start date""",
        default=None
    )
    enddate: typing.Optional[datetime.datetime] = strawberry.field(
        description="""Event end date""",
        default=None
    )
    # parent_id: typing.Optional[IDType] = strawberry.field(
    #     description="""Event parent id""",
    #     default=None
    # )
    changedby_id: strawberry.Private[IDType] = None

@strawberry.input(
    description="""Input type for deleting a Event"""
)
class EventDeleteGQLModel:
    id: IDType = strawberry.field(
        description="""Event id""",
    )
    lastchange: datetime.datetime = strawberry.field(
        description="""last change""",
    )

@strawberry.interface(
    description="""Event mutations"""
)
class EventMutation:
    @strawberry.mutation(
        description="""Insert a Event""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleInsertPermission[EventGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[UpdateError, EventGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[UpdateError, EventGQLModel](),
            RbacProviderExtension[UpdateError, EventGQLModel](),
            LoadDataExtension[UpdateError, EventGQLModel](
                getLoader=EventGQLModel.getLoader,
                primary_key_name="masterevent_id"
            )
        ],
    )
    async def event_insert(
        self,
        info: strawberry.Info,
        event: EventInsertGQLModel,
        db_row: typing.Any,
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
    ) -> typing.Union[EventGQLModel, InsertError[EventGQLModel]]:
        return await Insert[EventGQLModel].DoItSafeWay(info=info, entity=event)
    
    @strawberry.mutation(
        description="""Insert a plan, it could be connected to master plan, rbacobject_id is id of group the plan is for""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleInsertPermission[EventGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[UpdateError, EventGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[UpdateError, EventGQLModel](),
            RbacInsertProviderExtension[UpdateError, EventGQLModel](
                rbac_key_name="rbacobject_id"
            ),  
        ],
    )
    async def event_create_plan(
        self,
        info: strawberry.Info,
        event: EventPlanInsertGQLModel,
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
    ) -> typing.Union[EventGQLModel, InsertError[EventGQLModel]]:
        return await Insert[EventGQLModel].DoItSafeWay(info=info, entity=event)
    

    @strawberry.mutation(
        description="""Update a Event""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleUpdatePermission[EventGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[UpdateError, EventGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[UpdateError, EventGQLModel](),
            RbacProviderExtension[UpdateError, EventGQLModel](),
            LoadDataExtension[UpdateError, EventGQLModel]()
        ],
    )
    async def event_update(
        self,
        info: strawberry.Info,
        event: EventUpdateGQLModel
    ) -> typing.Union[EventGQLModel, UpdateError[EventGQLModel]]:
        return await Update[EventGQLModel].DoItSafeWay(info=info, entity=event)
    

    @strawberry.mutation(
        description="Accepts multiple invitations and if that invitations do not exist they are created",
        permission_classes=[
            OnlyForAuthentized
        ],
        extensions=[
            UserRoleProviderExtension[UpdateError, EventGQLModel](),
            RbacProviderExtension[UpdateError, EventGQLModel](),
            LoadDataExtension[UpdateError, EventGQLModel]()
        ]
    )
    async def event_ensure_invitations(
        self,
        info: strawberry.Info,
        event: EventEnsureUserInvitationsModel,
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
        db_row: typing.Any
    ) -> typing.Union[UpdateError[EventGQLModel], EventGQLModel]:
        return EventGQLModel.from_dataclass(db_row)
        pass

    @strawberry.mutation(
        description="Accepts multiple reservations and if that reservations do not exist they are created",
        permission_classes=[
            OnlyForAuthentized
        ],
        extensions=[
            UserRoleProviderExtension[UpdateError, EventGQLModel](),
            RbacProviderExtension[UpdateError, EventGQLModel](),
            LoadDataExtension[UpdateError, EventGQLModel]()
        ]            
    )
    async def event_ensure_reservations(
        self,
        info: strawberry.Info,
        event: EventEnsureFacilityReservationsModel,
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
        db_row: typing.Any
    ) -> typing.Union[UpdateError[EventGQLModel], EventGQLModel]:
        return EventGQLModel.from_dataclass(db_row)
        pass

    @strawberry.mutation(
        description="""Delete a Event""",
        permission_classes=[
            OnlyForAuthentized,
            # SimpleDeletePermission[EventGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[DeleteError, EventGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[DeleteError, EventGQLModel](),
            RbacProviderExtension[DeleteError, EventGQLModel](),
            LoadDataExtension[DeleteError, EventGQLModel]()
        ],
    )   
    async def event_delete(
        self,
        info: strawberry.Info,
        event: EventDeleteGQLModel
    ) -> typing.Optional[DeleteError[EventGQLModel]]:
        return await Delete[EventGQLModel].DoItSafeWay(info=info, entity=event)
    