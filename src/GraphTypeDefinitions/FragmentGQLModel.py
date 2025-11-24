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

from txtai import Embeddings
#local path to embedding model
embeddings = Embeddings(path="/home/filip/all-MiniLM-L6-v2")

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

    # text to be used for embedding (single large text field)
    content: typing.Optional[str] = strawberry.field(
        name="content",
        default=None,
        description="Plain text used to compute embeddings",
        permission_classes=[OnlyForAuthentized]
    )

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
    #TODO: FRAGMENT input filter
    #TODO: async funkce ktera vezme strukturu a spusti specificky sql dotaz nad ulozenymi radky
    # pgvector - semanticke dotazy - specialni SELECT
    #dekorovana async funkce
    #vstup: dotazovany text - return vector of fragments
    #primo sem
    #TODO: documentGQLModel - ma n fragmentu, pri semantickem dotazu na fragment se vracci
        # index nad dokumenty
        # u fragmentu cizi klic dokumentID
        # tabulka embeddeddocuments - konflikt s dokumentGQLModel ktery uz existuje
    #TODO: embedding z dotazu - content povinny, embedding volitelny, kdyz nebude tak se pocita
    #u open source modelu se musi obcas davat prefixy - pri ukladani do DB se ke content prida prefix
    fragment_vector_search: typing.List[FragmentGQLModel] = strawberry.field(
        description="""search fragments by vector similarity""",
        permission_classes=[OnlyForAuthentized],
        resolver=VectorResolver[FragmentGQLModel](fkey_field_name="vector", whereType=FragmentInputFilter)
    )

from uoishelpers.resolvers import TreeInputStructureMixin, InputModelMixin
@strawberry.input(
    description="""Input type for creating a Fragment"""
)


#pokud nejde o stromovou strukturu, tak tady musi byt InputModelMixin
class FragmentInsertGQLModel(InputModelMixin):
    getLoader = FragmentGQLModel.getLoader

    content: str = strawberry.field(
        description="""Text content to be embedded""",
    )

    rbacobject_id: IDType = strawberry.field(
        description="""Definitoin of access control"""
    )

    id: typing.Optional[IDType] = strawberry.field(
        description="""Fragment id""",
        default=None
    )

    vector: typing.Optional[typing.List[float]] = strawberry.field(
        description="""Semantic vector, will be computed from content if not provided""",
        default=None
    )

    createdby_id: strawberry.Private[IDType] = None


@strawberry.input(
    description="""Input type for updating a Fragment"""
)
class FragmentUpdateGQLModel:
    id: IDType = strawberry.field(
        description="""Event id""",
    )

    #not needed, rbac is taken from DB row and compared to user roles
    # rbacobject_id: IDType = strawberry.field(
    #     description="""Definitoin of access control"""
    # )

    content: typing.Optional[str] = strawberry.field(
        description="""Text content to be embedded""",
        default=None,
    )

    vector: typing.Optional[typing.List[float]] = strawberry.field(
        description="""Semantic vector, will be computed from content if not provided""",
        default=None
    )

    # parent_id: typing.Optional[IDType] = strawberry.field(
    #     description="""Event parent id""",
    #     default=None
    # )
    changedby_id: strawberry.Private[IDType] = None
    lastchange: datetime.datetime = strawberry.field(
        description="""last change""",
    )

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
            UserAccessControlExtension[InsertError, FragmentGQLModel](
                roles=[
                    "plánovací administrátor", 
                    "administrátor"
                ]
            ),
            UserRoleProviderExtension[InsertError, FragmentGQLModel](),
            RbacInsertProviderExtension[InsertError, FragmentGQLModel](
                rbac_key_name="rbacobject_id"    
            ),
        ],
    )
    async def fragment_insert(
        self,
        info: strawberry.Info,
        fragment: FragmentInsertGQLModel,
        # db_row: typing.Any, #not sure why this was neccessary, maybe has something to do with the removed extension above
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
    ) -> typing.Union[FragmentGQLModel, InsertError[FragmentGQLModel]]:
        # Auto-generate ID if not provided
        if getattr(fragment, "id", None) is None:
            import uuid as _uuid
            fragment.id = _uuid.uuid4()

        # print("user_roles in fragment_insert:", user_roles)

        
        # create vector from fragment.content using embeddings.transform
        try:
            vec = embeddings.transform(fragment.content)
            # handle both single vector or list-of-vectors - input arg je indexable
            if isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], (list, tuple)):
                vec = vec[0]
            fragment.vector = [float(x) for x in vec] if vec is not None else None
        except Exception:
            # on failure leave vector as-is (or None)
            fragment.vector = getattr(fragment, "vector", None)
        return await Insert[FragmentGQLModel].DoItSafeWay(info=info, entity=fragment)
    

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
                    "administrátor"
                ]
            ),
            UserRoleProviderExtension[UpdateError, FragmentGQLModel](),
            RbacProviderExtension[UpdateError, FragmentGQLModel](),
            LoadDataExtension[UpdateError, FragmentGQLModel]()
        ],
    )
    async def fragment_update(
        self,
        info: strawberry.Info,
        fragment: FragmentUpdateGQLModel,
        db_row: typing.Any,
        rbacobject_id: IDType,
        user_roles: typing.List[dict]
    ) -> typing.Union[FragmentGQLModel, UpdateError[FragmentGQLModel]]:
        return await Update[FragmentGQLModel].DoItSafeWay(info=info, entity=fragment)
    


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
                    "administrátor"
                ]
            ),
            UserRoleProviderExtension[DeleteError, FragmentGQLModel](),
            RbacProviderExtension[DeleteError, FragmentGQLModel](),
            LoadDataExtension[DeleteError, FragmentGQLModel]()
        ],
    )   
    async def fragment_delete(
        self,
        info: strawberry.Info,
        fragment: FragmentDeleteGQLModel,
        db_row: typing.Any,
        rbacobject_id: IDType,
        user_roles: typing.List[dict]
    ) -> typing.Optional[DeleteError[FragmentGQLModel]]:
        return await Delete[FragmentGQLModel].DoItSafeWay(info=info, entity=fragment)
    