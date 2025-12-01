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
UserGQLModel = typing.Annotated["UserGQLModel", strawberry.lazy(".UserGQLModel")]

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

    title: typing.Optional[str] = strawberry.field(
        name="title",
        default=None,
        description="Title of the document",
        permission_classes=[OnlyForAuthentized]
    )

    author_id: typing.Optional[IDType] = strawberry.field(
        name="author_id",
        default=None,
        description="ID of the document author (user)",
        permission_classes=[OnlyForAuthentized]
    )

    @strawberry.field(
        description="Author of the document (user entity via federation)",
        permission_classes=[OnlyForAuthentized]
    )
    def author(self, info: strawberry.types.Info) -> typing.Optional["UserGQLModel"]:
        """Resolve author as a federated User entity"""
        from .UserGQLModel import UserGQLModel
        if self.author_id is None:
            return None
        return UserGQLModel(id=self.author_id)

    classification: typing.Optional[str] = strawberry.field(
        name="classification",
        default=None,
        description="Classification of the document",
        permission_classes=[OnlyForAuthentized]
    )

    language: typing.Optional[str] = strawberry.field(
        name="language",
        default=None,
        description="Language of the document (e.g., 'en', 'cs', 'de')",
        permission_classes=[OnlyForAuthentized]
    )

    version: typing.Optional[str] = strawberry.field(
        name="version",
        default=None,
        description="Version identifier of the document",
        permission_classes=[OnlyForAuthentized]
    )

    source_url: typing.Optional[str] = strawberry.field(
        name="source_url",
        default=None,
        description="Source URL if document came from external source",
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

    title: typing.Optional[str] = strawberry.field(
        description="""Title of the document""",
        default=None
    )

    author_id: typing.Optional[IDType] = strawberry.field(
        description="""ID of the document author (user)""",
        default=None
    )

    classification: typing.Optional[str] = strawberry.field(
        description="""Classification of the document""",
        default="bez klasifikace"
    )

    language: typing.Optional[str] = strawberry.field(
        description="""Language of the document (e.g., 'en', 'cs', 'de')""",
        default=None
    )

    version: typing.Optional[str] = strawberry.field(
        description="""Version identifier of the document""",
        default=None
    )

    source_url: typing.Optional[str] = strawberry.field(
        description="""Source URL if document came from external source""",
        default=None
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
        description="""Document id""",
    )

    content: typing.Optional[str] = strawberry.field(
        description="""Text content to be embedded""",
        default=strawberry.UNSET,
    )

    title: typing.Optional[str] = strawberry.field(
        description="""Title of the document""",
        default=strawberry.UNSET,
    )

    author_id: typing.Optional[IDType] = strawberry.field(
        description="""ID of the document author (user)""",
        default=strawberry.UNSET,
    )

    language: typing.Optional[str] = strawberry.field(
        description="""Language of the document (e.g., 'en', 'cs', 'de')""",
        default=strawberry.UNSET,
    )

    version: typing.Optional[str] = strawberry.field(
        description="""Version identifier of the document""",
        default=strawberry.UNSET,
    )

    source_url: typing.Optional[str] = strawberry.field(
        description="""Source URL if document came from external source""",
        default=strawberry.UNSET,
    )

    changedby_id: strawberry.Private[IDType] = None
    lastchange: datetime.datetime = strawberry.field(
        description="""last change""",
    )

@strawberry.input(
    description="""Input type for updating Document classification (restricted to certain roles)"""
)
class DocumentUpdateClassificationGQLModel:
    id: IDType = strawberry.field(
        description="""Document id""",
    )

    classification: typing.Optional[str] = strawberry.field(
        description="""Classification or category of the document""",
        default=strawberry.UNSET,
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
        description="""Update Document classification (restricted to specific roles)""",
        permission_classes=[
            OnlyForAuthentized
        ],
        extensions=[
            UserAccessControlExtension[UpdateError, DocumentGQLModel](
                roles=[
                    "administrátor",  # Only administrators can update classification
                ]
            ),
            UserRoleProviderExtension[UpdateError, DocumentGQLModel](),
            RbacProviderExtension[UpdateError, DocumentGQLModel](),
            LoadDataExtension[UpdateError, DocumentGQLModel]()
        ],
    )
    async def Document_update_classification(
        self,
        info: strawberry.Info,
        Document: DocumentUpdateClassificationGQLModel,
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
    