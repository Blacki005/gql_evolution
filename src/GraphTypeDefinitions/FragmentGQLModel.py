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

@createInputs2
class FragmentInputFilter:
    id: IDType
    valid: bool


@strawberry.federation.type(
    description="""Entity representing a Fragment of document""",
    keys=["id"]
)
class FragmentGQLModel(BaseGQLModel):
    @classmethod
    def getLoader(cls, info: strawberry.types.Info):
        return getLoadersFromInfo(info).FragmentModel

    path: typing.Optional[str] = strawberry.field(
        description="""Materialized path representing the group's hierarchical location.  
Materializovaná cesta reprezentující umístění skupiny v hierarchii.""",
        default=None,
        permission_classes=[OnlyForAuthentized]
    )


    vector: typing.Optional[typing.List[float]] = strawberry.field(
        name="vector",
        default=lambda: [0.0] * 1024,
        description="semantic vector, default is 1024 zeros",
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

@strawberry.interface(
    description="""Event queries"""
)
class FragmentQuery:
    fragment_by_id: typing.Optional[FragmentGQLModel] = strawberry.field(
        description="""get a fragment by its id""",
        permission_classes=[OnlyForAuthentized],
        resolver=FragmentGQLModel.load_with_loader
    )

    fragment_page: typing.List[FragmentGQLModel] = strawberry.field(
        description="""get a page of fragments""",
        permission_classes=[OnlyForAuthentized],
        resolver=PageResolver[FragmentGQLModel](whereType=FragmentInputFilter)
    )

from uoishelpers.resolvers import TreeInputStructureMixin, InputModelMixin
@strawberry.input(
    description="""Input type for creating a Fragment"""
)



class FragmentInsertGQLModel(TreeInputStructureMixin):
    getLoader = FragmentGQLModel.getLoader

    id: typing.Optional[IDType] = strawberry.field(
        description="""Event id""",
        default=None
    )

    rbacobject_id: strawberry.Private[IDType] = None
    createdby_id: strawberry.Private[IDType] = None


@strawberry.input(
    description="""Input type for updating a Fragment"""
)
class FragmentUpdateGQLModel:
    id: IDType = strawberry.field(
        description="""Event id""",
    )
    lastchange: datetime.datetime = strawberry.field(
        description="timestamp"
    )
    # parent_id: typing.Optional[IDType] = strawberry.field(
    #     description="""Event parent id""",
    #     default=None
    # )
    changedby_id: strawberry.Private[IDType] = None

@strawberry.input(
    description="""Input type for deleting a Fragment"""
)
class FragmentDeleteGQLModel:
    id: IDType = strawberry.field(
        description="""Fragment id""",
    )
    lastchange: datetime.datetime = strawberry.field(
        description="""last change""",
    )

@strawberry.interface(
    description="""Fragment mutations"""
)
class FragmentMutation:
    @strawberry.mutation(
        description="""Insert a Fragment""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleInsertPermission[FragmentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[UpdateError, FragmentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[UpdateError, FragmentGQLModel](),
            RbacProviderExtension[UpdateError, FragmentGQLModel](),
            LoadDataExtension[UpdateError, FragmentGQLModel](
                getLoader=FragmentGQLModel.getLoader,
                primary_key_name="masterevent_id"
            )
        ],
    )
    async def event_insert(
        self,
        info: strawberry.Info,
        event: FragmentInsertGQLModel,
        db_row: typing.Any,
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
    ) -> typing.Union[FragmentGQLModel, InsertError[FragmentGQLModel]]:
        return await Insert[FragmentGQLModel].DoItSafeWay(info=info, entity=event)
    


    @strawberry.mutation(
        description="""Update a Fragment""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleUpdatePermission[FragmentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[UpdateError, FragmentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[UpdateError, FragmentGQLModel](),
            RbacProviderExtension[UpdateError, FragmentGQLModel](),
            LoadDataExtension[UpdateError, FragmentGQLModel]()
        ],
    )
    async def event_update(
        self,
        info: strawberry.Info,
        event: FragmentUpdateGQLModel
    ) -> typing.Union[FragmentGQLModel, UpdateError[FragmentGQLModel]]:
        return await Update[FragmentGQLModel].DoItSafeWay(info=info, entity=event)
    


    @strawberry.mutation(
        description="""Delete a Fragment""",
        permission_classes=[
            OnlyForAuthentized,
            # SimpleDeletePermission[FragmentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[DeleteError, FragmentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    # "personalista"
                ]
            ),
            UserRoleProviderExtension[DeleteError, FragmentGQLModel](),
            RbacProviderExtension[DeleteError, FragmentGQLModel](),
            LoadDataExtension[DeleteError, FragmentGQLModel]()
        ],
    )   
    async def event_delete(
        self,
        info: strawberry.Info,
        event: FragmentDeleteGQLModel
    ) -> typing.Optional[DeleteError[FragmentGQLModel]]:
        return await Delete[FragmentGQLModel].DoItSafeWay(info=info, entity=event)
    