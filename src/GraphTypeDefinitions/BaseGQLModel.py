import uuid
import datetime
import typing
import strawberry
import dataclasses

from uoishelpers.gqlpermissions import OnlyForAuthentized, RBACObjectGQLModel

IDType = uuid.UUID
UserGQLModel = typing.Annotated["UserGQLModel", strawberry.lazy(".UserGQLModel")]



from strawberry.federation.schema_directive import schema_directive, Location
from strawberry.directive import DirectiveLocation
@schema_directive(
    repeatable=True,
    compose=True,
    description="Description for foreign keys",
    locations=[Location.INPUT_FIELD_DEFINITION, Location.FIELD_DEFINITION, DirectiveLocation.FIELD],
)
class Relation:
    """
    @relation(to: Typ, field: 'id')
    říká, že pole inputu je cizí klíč na zadaný typ.
    """
    to: str
    field: str = "id"

@classmethod
async def resolve_reference(cls, info: strawberry.types.Info, id: IDType, **otherData):
    _id = IDType(id) if isinstance(id, str) else id
    return None if id is None else cls(id=_id, **otherData)


@strawberry.federation.interface(
    description="""Entity representing an interface"""
)
class BaseGQLModel:
    
    @classmethod
    def getLoader(cls, info: strawberry.types.Info):
        raise NotImplementedError()
    
    @classmethod
    def from_dataclass(cls, db_row):
        db_row_dict = dataclasses.asdict(db_row)
        print(f"from_dataclass: {db_row_dict}")
        instance = cls(**db_row_dict)
        return instance

    @classmethod
    async def load_with_loader(cls, info: strawberry.types.Info, id: uuid.UUID):
        if id is None: return None

        _id = IDType(id) if isinstance(id, str) else id
        loader = cls.getLoader(info=info)
        db_row = await loader.load(_id)
        
        return cls(id=id) if db_row is None else cls.from_dataclass(db_row=db_row)
    
    @classmethod
    async def resolve_reference(cls, info: strawberry.types.Info, id: uuid.UUID, **otherdata):
        return await cls.load_with_loader(info=info, id=id)
       
    id: IDType = strawberry.field(
        description="primary key", 
        permission_classes=[OnlyForAuthentized]
        )
    lastchange: typing.Optional[datetime.datetime] = strawberry.field(
        description="timestamp", 
        default=None,
        permission_classes=[OnlyForAuthentized]
        )
    created: typing.Optional[datetime.datetime] = strawberry.field(
        description="date & time of unit born", 
        default=None,
        permission_classes=[OnlyForAuthentized]
        )
    createdby_id: typing.Optional[IDType] = strawberry.field(
        description="who created this entity", 
        default=None,
        permission_classes=[OnlyForAuthentized]
        )
    changedby_id: typing.Optional[IDType] = strawberry.field(
        description="who changed this entity", 
        default=None,
        permission_classes=[OnlyForAuthentized]
        )
    rbacobject_id: typing.Optional[IDType] = strawberry.field(
        description="rbac ruling object", 
        default=None,
        permission_classes=[OnlyForAuthentized]
        )

    @strawberry.field(
        description="who created this entity",
        permission_classes=[OnlyForAuthentized]
        )
    async def createdby(self) -> typing.Optional["UserGQLModel"]:
        from .UserGQLModel import UserGQLModel
        return None if self.createdby_id is None else UserGQLModel(id=self.createdby_id)

    @strawberry.field(
        description="who changed this entity",
        permission_classes=[OnlyForAuthentized]
        )
    async def changedby(self) -> typing.Optional["UserGQLModel"]:
        from .UserGQLModel import UserGQLModel
        return None if self.changedby_id is None else UserGQLModel(id=self.changedby_id)

    @strawberry.field(
        description="rbac ruling object",
        permission_classes=[OnlyForAuthentized]
        )
    async def rbacobject(self) -> typing.Optional["RBACObjectGQLModel"]:
        return None if self.rbacobject_id is None else RBACObjectGQLModel(id=self.rbacobject_id)
