import datetime
import strawberry

from .query import Query
from .mutation import Mutation

timedelta = strawberry.scalar(
    # NewType("TimeDelta", float),
    datetime.timedelta,
    name="timedelta",
    serialize=lambda v: v.total_seconds() / 60,
    parse_value=lambda v: datetime.timedelta(minutes=v),
)


from .BaseGQLModel import Relation
from .BaseGQLModel import BaseGQLModel
from .UserGQLModel import UserGQLModel

schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    types=(UserGQLModel, BaseGQLModel), 
    scalar_overrides={datetime.timedelta: timedelta._scalar_definition},

    extensions=[],
    schema_directives=[Relation]
    
)

from uoishelpers.schema import WhoAmIExtension, ProfilingExtension, PrometheusExtension
schema.extensions.append(WhoAmIExtension)
# schema.extensions.append(ProfilingExtension)
schema.extensions.append(PrometheusExtension(prefix="GQL_Evolution"))

from uoishelpers.gqlpermissions.RolePermissionSchemaExtension import RolePermissionSchemaExtension
schema.extensions.append(RolePermissionSchemaExtension)

