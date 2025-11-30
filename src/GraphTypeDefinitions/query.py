import strawberry

from .EventGQLModel import EventQuery
from .EventInvitationGQLModel import EventInvitationQuery
from .FragmentGQLModel import FragmentQuery
from .DocumentGQLModel import DocumentQuery

@strawberry.type(description="""Type for query root""")
class Query(EventQuery, EventInvitationQuery, FragmentQuery, DocumentQuery):
    @strawberry.field(
        description="""Returns hello world"""
        )
    async def hello(
        self,
        info: strawberry.types.Info,
    ) -> str:
        return "hello world"
