import strawberry


from .EventGQLModel import EventMutation
from .EventInvitationGQLModel import EventInvitationMutation
from .FragmentGQLModel import FragmentMutation
from .DocumentGQLModel import DocumentMutation

@strawberry.type(description="""Type for mutation root""")
class Mutation(EventMutation, EventInvitationMutation, FragmentMutation, DocumentMutation):
    pass

