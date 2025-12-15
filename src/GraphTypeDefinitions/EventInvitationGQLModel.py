import asyncio
import dataclasses
import datetime
import typing
import strawberry

from uoishelpers.gqlpermissions import (
    OnlyForAuthentized,
    SimpleInsertPermission, 
    SimpleUpdatePermission, 
    SimpleDeletePermission
)    
from uoishelpers.resolvers import (
    getLoadersFromInfo, 
    getUserFromInfo,
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

from .BaseGQLModel import BaseGQLModel, IDType


EventGQLModel = typing.Annotated["EventGQLModel", strawberry.lazy(".EventGQLModel")]
EventInputFilter = typing.Annotated["EventInputFilter", strawberry.lazy(".EventGQLModel")]
UserGQLModel = typing.Annotated["UserGQLModel", strawberry.lazy(".UserGQLModel")]

@createInputs2
class EventInvitationInputFilter:
    id: IDType
    event_id: IDType
    user_id: IDType
    state_id: IDType

    event: EventInputFilter = strawberry.field(description="""Event filter operators, 
for field "event" the filters could be
{"event": {"start_date": {"_ge": "2025-06-30T18:01:59"}}}
{"event": {"end_date": {"_le": "2025-06-30T18:01:59"}}}
{"event": {"_and": [{"start_date": {"_ge": "2025-06-30T18:01:59"}}, {"end_date": {"_le": "2025-06-30T18:01:59"}}]}}
""")

@strawberry.federation.type(
    keys=["id"], description="""Entity representing a Invitation to an Event and also presence of a user, invitation state and presence is managed by state"""
)
class EventInvitationGQLModel(BaseGQLModel):

    @classmethod
    def getLoader(cls, info: strawberry.types.Info):
        return getLoadersFromInfo(info).EventInvitationModel

    event_id: typing.Optional[IDType] = strawberry.field(
        description="""Event assigned to the invitation""",
        default=None,
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    user_id: typing.Optional[IDType] = strawberry.field( 
        description="""User assigned to the invitation""",
        default=None,
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    state_id: typing.Optional[IDType] = strawberry.field(
        description="""State assigned to the invitation""",
        default=None,
        permission_classes=[
            OnlyForAuthentized  
        ]
    )

    event: typing.Optional[EventGQLModel] = strawberry.field(
        description="""Event assigned to the invitation""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=ScalarResolver[EventGQLModel](fkey_field_name="event_id")
    )

    user: typing.Optional[UserGQLModel] = strawberry.field(
        description="""User assigned to the invitation""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=ScalarResolver[UserGQLModel](fkey_field_name="user_id")
    )

@strawberry.type(description="")
class EventInvitationQuery:

    event_invitation_by_id: typing.Optional[EventInvitationGQLModel] = strawberry.field(
        description="Invitation by its id",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=EventInvitationGQLModel.load_with_loader
    )

    event_invitation_page: typing.List[EventInvitationGQLModel] = strawberry.field(
        description="selected invitations to events",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=PageResolver[EventInvitationGQLModel](whereType=EventInvitationInputFilter)
    )


from uoishelpers.resolvers import InputModelMixin
@strawberry.input(
    description="""EventInvitation insert mutation"""
)
class EventInvitationInsertGQLModel(InputModelMixin):
    getLoader = EventInvitationGQLModel.getLoader
    event_id: typing.Optional[IDType] = strawberry.field(
        description="event id to which invitation is sent",
        default=None,
    )

    user_id: typing.Optional[IDType] = strawberry.field(
        description="user id who receive invitation",
        default=None,
    )

    state_id: typing.Optional[IDType] = strawberry.field(
        description="invitation kind",
        default=None
    )

    id: typing.Optional[IDType] = strawberry.field(
        description="""client generated id""",
        default=None,
    )

@strawberry.input(
    description="""EventInvitation update mutation"""
)
class EventInvitationUpdateGQLModel:
    id: IDType = strawberry.field(
        description="""id"""
    )

    lastchange: datetime.datetime = strawberry.field(
        description="""timestamp"""
    )

    state_id: typing.Optional[IDType] = strawberry.field(
        description="invitation kind and presence type",
        default=None
    )

    # user_id: typing.Optional[IDType] = strawberry.field(
    #     description="user id who receive invitation",
    #     default=None,
    # )

    changedby_id: strawberry.Private[IDType] = None

@strawberry.input(
    description="""EventInvitation delete mutation"""
)
class EventInvitationDeleteGQLModel:
    id: IDType = strawberry.field(
        description="""EventInvitation id"""
    )
    lastchange: datetime.datetime = strawberry.field(
        description="""EventInvitation lastchange"""
    )


@strawberry.type(
    description="""EventInvitation mutation"""
)
class EventInvitationMutation:
    from .EventGQLModel import EventGQLModel
    # @strawberry.field(
    #     description="""Insert a EventInvitation""",
    #     permission_classes=[
    #         OnlyForAuthentized
    #         # SimpleInsertPermission[EventGQLModel](roles=["administrátor"])
    #     ],
    #     extensions=[
    #         # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
    #         UserAccessControlExtension[InsertError, EventInvitationGQLModel](
    #             roles=[
    #                 "plánovací administrátor", 
    #                 # "personalista"
    #             ]
    #         ),
    #         UserRoleProviderExtension[InsertError, EventInvitationGQLModel](),
    #         RbacProviderExtension[InsertError, EventInvitationGQLModel](),
    #         LoadDataExtension[InsertError, EventInvitationGQLModel](
    #             getLoader=EventGQLModel.getLoader,
    #             primary_key_name="event_id"
    #         )
    #     ],
    # )
    # async def event_invitation_insert(
    #     self,
    #     info: strawberry.types.Info,
    #     invitation: EventInvitationInsertGQLModel,
    #     db_row: typing.Any,
    #     rbacobject_id: IDType,
    #     user_roles: typing.List[dict],
    # ) -> typing.Union[EventInvitationGQLModel, InsertError[EventInvitationGQLModel]]:
    #     # TODO check if invitation already exists and reject to invite that user again
    #     return await Insert[EventInvitationGQLModel].DoItSafeWay(info=info, entity=invitation)
    
    @strawberry.field(
        description="""Allows invited user to accept or decline the invitation""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleInsertPermission[EventGQLModel](roles=["administrátor"])
        ],
        extensions=[
            LoadDataExtension[UpdateError, EventInvitationGQLModel]()
        ],
    )
    async def event_invitation_accept_decline(
        self,
        info: strawberry.types.Info,
        invitation: EventInvitationUpdateGQLModel,
        db_row: typing.Any,
    ) -> typing.Union[EventInvitationGQLModel, UpdateError[EventInvitationGQLModel]]:
        user = getUserFromInfo(info=info)
        if user["id"] == db_row.user_id:
            possible_values = set(
                IDType('7d2ef223-b60e-4e6d-b7d5-5fdc1f8e2ec2'), # 'accepted'
                IDType('d6a5e9e4-3e47-4c95-a4aa-b194dd2bc3a7'), # 'declined',  
            )
            if invitation.state_id in possible_values:
                return await Update[EventInvitationGQLModel].DoItSafeWay(info=info, entity=invitation)
        return UpdateError[EventInvitationGQLModel](
            _entity=db_row,
            msg="You are not authorized",
            code="48f0a626-f31a-4429-9e53-819ca865786d",
            location="event_invitation_accept_decline",
            _input=invitation
        )
        

    @strawberry.mutation(
        description="""Update the EventInvitation, caller must be organizer of the event""",
        permission_classes=[
            OnlyForAuthentized
        ],
        extensions=[
            LoadDataExtension[UpdateError, EventInvitationGQLModel]()
        ],
    )
    async def event_invitation_update(
        self,
        info: strawberry.types.Info,
        invitation: EventInvitationUpdateGQLModel,
        db_row: typing.Any,
        # rbacobject_id: IDType,
        # user_roles: typing.List[dict],
    ) -> typing.Union[EventInvitationGQLModel, UpdateError[EventInvitationGQLModel]]:
        loader = EventInvitationGQLModel.getLoader(info=info)
        event_invitations = await loader.filter_by(event_id=db_row.event_id)
        user = getUserFromInfo(info=info)
        user_id = user["id"]
        organizer_id = IDType("3265a488-bbfa-4c59-946c-7a7b059ee4f0")
        user_organizer_invitations = list(filter(
            lambda row: row.user_id == user_id and row.state_id == organizer_id,
            event_invitations
        ))
        if user_organizer_invitations:
            return await Update[EventInvitationGQLModel].DoItSafeWay(info=info, entity=invitation)        
        return UpdateError[EventInvitationGQLModel](
            _entity=db_row,
            msg="You are not organizer",
            code="ae30e32b-94ec-4d59-9c1e-7eca3b75701e",
            location="event_invitation_update",
            _input=invitation
        )


    @strawberry.field(
        description="""Delete a EventInvitation""",
        permission_classes=[
            SimpleDeletePermission[EventInvitationGQLModel](roles=["administrátor"])
        ]
    )
    async def event_invitation_delete(
        self,
        info: strawberry.types.Info,
        invitation: EventInvitationDeleteGQLModel
    ) -> typing.Optional[DeleteError[EventInvitationGQLModel]]:
        return await Delete[EventInvitationGQLModel].DoItSafeWay(info=info, entity=invitation)        