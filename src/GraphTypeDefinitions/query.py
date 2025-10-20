import strawberry

from .EventGQLModel import EventQuery
from .EventInvitationGQLModel import EventInvitationQuery
from .FragmentGQLModel import FragmentQuery

@strawberry.type(description="""Type for query root""")
class Query(EventQuery, EventInvitationQuery, FragmentQuery):
    @strawberry.field(
        description="""Returns hello world"""
        )
    async def hello(
        self,
        info: strawberry.types.Info,
    ) -> str:
        return "hello world"
