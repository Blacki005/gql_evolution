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

FragmentGQLModel = typing.Annotated["FragmentGQLModel", strawberry.lazy(".FragmentGQLModel")]
FragmentInputFilter = typing.Annotated["FragmentInputFilter", strawberry.lazy(".FragmentGQLModel")]

@createInputs2
class DocumentInputFilter:
    id: IDType
    valid: bool


@strawberry.federation.type(
    description="""Entity representing a Document""",
    keys=["id"]
)
class DocumentGQLModel(BaseGQLModel):
    @classmethod
    def getLoader(cls, info: strawberry.types.Info):
        return getLoadersFromInfo(info).DocumentModel

    content: typing.Optional[str] = strawberry.field(
        name="content",
        default=None,
        description="Plain text of the document",
        permission_classes=[OnlyForAuthentized]
    )

    fragments: typing.List["FragmentGQLModel"] = strawberry.field(
        description="""Fragments of the document""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=VectorResolver["FragmentGQLModel"](fkey_field_name="document_id", whereType=FragmentInputFilter)
    )

@strawberry.interface(
    description="""Document queries"""
)
class DocumentQuery:
    document_by_id: typing.Optional[DocumentGQLModel] = strawberry.field(
        description="""get a Document by its id""",
        permission_classes=[OnlyForAuthentized],
        resolver=DocumentGQLModel.load_with_loader
    )

    document_page: typing.List[DocumentGQLModel] = strawberry.field(
        description="""get a page of Documents""",
        permission_classes=[OnlyForAuthentized],
        resolver=PageResolver[DocumentGQLModel](whereType=DocumentInputFilter)
    )


from uoishelpers.resolvers import TreeInputStructureMixin, InputModelMixin
@strawberry.input(
    description="""Input type for creating a document"""
)


#pokud nejde o stromovou strukturu, tak tady musi byt InputModelMixin
class DocumentInsertGQLModel(InputModelMixin):
    getLoader = DocumentGQLModel.getLoader

    content: str = strawberry.field(
        description="""Text content""",
    )

    rbacobject_id: IDType = strawberry.field(
        description="""Definitoin of access control"""
    )

    id: typing.Optional[IDType] = strawberry.field(
        description="""Document id""",
        default=None
    )

    createdby_id: strawberry.Private[IDType] = None


@strawberry.input(
    description="""Input type for updating a Document"""
)
class DocumentUpdateGQLModel:
    id: IDType = strawberry.field(
        description="""Event id""",
    )

    content: typing.Optional[str] = strawberry.field(
        description="""Text content to be embedded""",
        default=None,
    )

    changedby_id: strawberry.Private[IDType] = None
    lastchange: datetime.datetime = strawberry.field(
        description="""last change""",
    )

@strawberry.input(
    description="""Input type for deleting a Document"""
)
class DocumentDeleteGQLModel:
    id: IDType = strawberry.field(
        description="""Document id""",
    )
    lastchange: datetime.datetime = strawberry.field(
        description="""last change""",
    )

@strawberry.interface(
    description="""Document mutations"""
)
class DocumentMutation:
    @strawberry.mutation(
        description="""Insert a Document""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleInsertPermission[DocumentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[InsertError, DocumentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    "administrátor"
                ]
            ),
            UserRoleProviderExtension[InsertError, DocumentGQLModel](),
            RbacInsertProviderExtension[InsertError, DocumentGQLModel](
                rbac_key_name="rbacobject_id"    
            ),
        ],
    )
    async def Document_insert(
        self,
        info: strawberry.Info,
        Document: DocumentInsertGQLModel,
        # db_row: typing.Any, #not sure why this was neccessary, maybe has something to do with the removed extension above
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
    ) -> typing.Union[DocumentGQLModel, InsertError[DocumentGQLModel]]:
        # Auto-generate ID if not provided
        if getattr(Document, "id", None) is None:
            import uuid as _uuid
            Document.id = _uuid.uuid4()
        return await Insert[DocumentGQLModel].DoItSafeWay(info=info, entity=Document)
    

    @strawberry.mutation(
        description="""Update a Document""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleUpdatePermission[DocumentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[UpdateError, DocumentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    "administrátor"
                ]
            ),
            UserRoleProviderExtension[UpdateError, DocumentGQLModel](),
            RbacProviderExtension[UpdateError, DocumentGQLModel](),
            LoadDataExtension[UpdateError, DocumentGQLModel]()
        ],
    )
    async def Document_update(
        self,
        info: strawberry.Info,
        Document: DocumentUpdateGQLModel,
        db_row: typing.Any,
        rbacobject_id: IDType,
        user_roles: typing.List[dict]
    ) -> typing.Union[DocumentGQLModel, UpdateError[DocumentGQLModel]]:
        return await Update[DocumentGQLModel].DoItSafeWay(info=info, entity=Document)
    


    @strawberry.mutation(
        description="""Delete a Document""",
        permission_classes=[
            OnlyForAuthentized,
            # SimpleDeletePermission[DocumentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[DeleteError, DocumentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    "administrátor"
                ]
            ),
            UserRoleProviderExtension[DeleteError, DocumentGQLModel](),
            RbacProviderExtension[DeleteError, DocumentGQLModel](),
            LoadDataExtension[DeleteError, DocumentGQLModel]()
        ],
    )   
    async def Document_delete(
        self,
        info: strawberry.Info,
        Document: DocumentDeleteGQLModel,
        db_row: typing.Any,
        rbacobject_id: IDType,
        user_roles: typing.List[dict]
    ) -> typing.Optional[DeleteError[DocumentGQLModel]]:
        return await Delete[DocumentGQLModel].DoItSafeWay(info=info, entity=Document)
    