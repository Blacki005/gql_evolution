import datetime
import typing
import strawberry

import strawberry.types
from uoishelpers.gqlpermissions import (
    OnlyForAuthentized
)    
from uoishelpers.resolvers import (
    getLoadersFromInfo,
    createInputs2,

    InsertError, 
    Insert, 
    UpdateError, 
    Update, 
    DeleteError, 
    Delete,

    PageResolver,
    ScalarResolver
)
from uoishelpers.gqlpermissions.LoadDataExtension import LoadDataExtension
from uoishelpers.gqlpermissions.RbacProviderExtension import RbacProviderExtension
from uoishelpers.gqlpermissions.UserRoleProviderExtension import UserRoleProviderExtension
from uoishelpers.gqlpermissions.UserAccessControlExtension import UserAccessControlExtension

from .BaseGQLModel import BaseGQLModel, IDType

DocumentGQLModel = typing.Annotated["DocumentGQLModel", strawberry.lazy(".DocumentGQLModel")]
DocumentInputFilter = typing.Annotated["DocumentInputFilter", strawberry.lazy(".DocumentGQLModel")]


from txtai import Embeddings
import os

# Get the project root directory (where main.py is located)
# This works both locally and in Docker container
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(PROJECT_ROOT, "all-MiniLM-L6-v2")

# Initialize embeddings with absolute path to local model
# IMPORTANT: This creates a global embeddings instance loaded at module import time
# Pros: Fast access, model loaded once, thread-safe for read operations
# Cons: Uses memory even if not used, slow startup, potential issues in multiprocessing
# The model (all-MiniLM-L6-v2) produces 384-dimensional vectors
embeddings = Embeddings(path=MODEL_PATH)

# Import error codes for consistent error handling
from .error_codes import (
    FRAGMENT_INSERT_EMBEDDING_FAILED,
    FRAGMENT_UPDATE_EMBEDDING_FAILED,
)

@createInputs2
class FragmentInputFilter:
    content: str
    document_id: IDType
    created: datetime.datetime
    lastchange: datetime.datetime
    id: IDType
    valid: bool
    document: DocumentInputFilter = strawberry.field(description="""Document filter operators, 
for field "document" the filters could be
{"document": {"title": {"_ilike": "%keyword%"}}}
{"document": {"author_id": {"_eq": "ce22d5ab-f867-4cf1-8e3c-ee77eab81c24"}}}
{"document": {"_and": [{"classification": {"_eq": "bez utajení"}}, {"language": {"_eq": "cs"}}]}}
""")

@strawberry.federation.type(
    description="""Entity representing a Fragment of document""",
    keys=["id"]
)
class FragmentGQLModel(BaseGQLModel):
    @classmethod
    def getLoader(cls, info: strawberry.types.Info):
        return getLoadersFromInfo(info).FragmentModel


    document_id: typing.Optional[IDType] = strawberry.field(
        default=None,
        description="""Document that the fragment belongs to""",
        permission_classes=[
            OnlyForAuthentized
        ]
    )

    document: typing.Optional[DocumentGQLModel] = strawberry.field(
        description="""Document that the fragment originates from""",
        permission_classes=[
            OnlyForAuthentized
        ],
        resolver=ScalarResolver[DocumentGQLModel](fkey_field_name="document_id")
    )

    vector: typing.Optional[typing.List[float]] = strawberry.field(
        name="vector",
        default=None,
        description="semantic vector, None if not computed",
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

    @strawberry.field(
        description="""Search fragments by semantic similarity using vector embeddings""",
        permission_classes=[OnlyForAuthentized]
    )
    async def fragment_vector_search(
        self,
        info: strawberry.types.Info,
        query_text: typing.Optional[str] = None,
        query_vector: typing.Optional[typing.List[float]] = None,
        limit: int = 10,
        threshold: float = 0.855
    ) -> typing.List[FragmentGQLModel]:
        """
        Search for fragments by semantic similarity.
        
        Args:
            query_text: Text to search for (will be converted to embedding vector)
            query_vector: Pre-computed embedding vector (384 dimensions)
            limit: Maximum number of results to return
            threshold: Maximum cosine distance for results (0=identical, 2=opposite).
                      Default 0.5. Lower = stricter. Typical range: 0.3-0.7
            
        Returns:
            List of semantically related fragments (within threshold distance)
        """
        import sqlalchemy
        from src.DBDefinitions import FragmentModel
        
        # Get database session from loader
        loader = getLoadersFromInfo(info).FragmentModel
        session = loader.session
        
        # Determine which vector to use for search
        # Either convert text to embedding or use provided vector directly
        if query_text is not None:
            # Generate embedding from text using all-MiniLM-L6-v2
            # This produces a 384-dimensional vector for semantic comparison
            search_vector = embeddings.transform(query_text)
        elif query_vector is not None:
            # Use pre-computed vector (must be 384 dimensions for compatibility)
            search_vector = query_vector
        else:
            # No input provided, return empty list
            from graphql import GraphQLError
            raise GraphQLError("Either 'query_text' or 'query_vector' must be provided for vector search")
        
        # Execute vector similarity search using pgvector extension
        # pgvector's cosine distance: 0 = identical vectors, 2 = opposite vectors
        # Lower threshold = stricter matching (more similar results)
        # Higher threshold = looser matching (more diverse results)
        stmt = (
            sqlalchemy.select(FragmentModel)
            .filter(FragmentModel.vector.isnot(None))  # Only search fragments with vectors
            .filter(FragmentModel.vector.cosine_distance(search_vector) <= threshold)  # Apply similarity threshold
            .order_by(FragmentModel.vector.cosine_distance(search_vector))  # Order by similarity (most similar first)
            .limit(limit)  # Limit number of results
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        
        # Convert DB rows to GraphQL models using from_dataclass
        return [FragmentGQLModel.from_dataclass(row) for row in rows]


from uoishelpers.resolvers import TreeInputStructureMixin, InputModelMixin
@strawberry.input(
    description="""Input type for creating a Fragment"""
)


#pokud nejde o stromovou strukturu, tak tady musi byt InputModelMixin
class FragmentInsertGQLModel(InputModelMixin):
    getLoader = FragmentGQLModel.getLoader

    document_id: typing.Optional[IDType] = strawberry.field(
        default=None,
        description="""document id to which fragment belongs""",
    )

    content: str = strawberry.field(
        description="""Text content to be embedded""",
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

    content: typing.Optional[str] = strawberry.field(
        description="""Text content to be embedded""",
        default=strawberry.UNSET,
    )

    vector: typing.Optional[typing.List[float]] = strawberry.field(
        description="""Semantic vector, will be computed from content if not provided""",
        default=strawberry.UNSET,
    )

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

@strawberry.type(
    description="""Fragment mutations"""
)
class FragmentMutation:
    from .DocumentGQLModel import DocumentGQLModel
    @strawberry.field(
        description="""Insert a Fragment""",
        permission_classes=[
            OnlyForAuthentized
            # SimpleInsertPermission[FragmentGQLModel](roles=["administrátor"])
        ],
        extensions=[
            # UpdatePermissionCheckRoleFieldExtension[GroupGQLModel](roles=["administrátor", "personalista"]),
            UserAccessControlExtension[InsertError, FragmentGQLModel](
                roles=[
                    "administrátor",
                    "zpracovatel gdpr",
                    "rektor",
                    "prorektor",
                    "děkan",
                    "proděkan",
                    "vedoucí katedry",
                    "vedoucí učitel",
                    "garant" 
                ]
            ),
            UserRoleProviderExtension[InsertError, FragmentGQLModel](),
            RbacProviderExtension[InsertError, FragmentGQLModel](),
            LoadDataExtension[InsertError, FragmentGQLModel](
                getLoader=DocumentGQLModel.getLoader,
                primary_key_name="document_id"
            )
        ],
    )
    async def fragment_insert(
        self,
        info: strawberry.Info,
        fragment: FragmentInsertGQLModel,
        db_row: typing.Any, #not sure why this was neccessary, maybe has something to do with the removed extension above
        rbacobject_id: IDType,
        user_roles: typing.List[dict],
    ) -> typing.Union[FragmentGQLModel, InsertError[FragmentGQLModel]]:
        # Auto-generate ID if not provided
        if getattr(fragment, "id", None) is None:
            import uuid as _uuid
            fragment.id = _uuid.uuid4()
        
        # Generate embedding vector from text content using txtai
        # The global embeddings model transforms text into 384-dimensional vectors
        try:
            vec = embeddings.transform(fragment.content)
            
            # Handle txtai's inconsistent return formats:
            # Sometimes returns: [vector] (list containing one vector)
            # Sometimes returns: [[vector]] (nested list)
            # We need just the vector itself: [float, float, ...]
            if isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], (list, tuple)):
                vec = vec[0]  # Extract the inner vector from nested structure
                
            # Convert to list of floats for database storage (pgvector format)
            fragment.vector = [float(x) for x in vec] if vec is not None else None
            
        except Exception as e:
            # Embedding generation can fail due to:
            # - Model loading issues
            # - Out of memory
            # - Invalid text input
            # - txtai library errors
            print(f"[Fragment Insert] Embedding generation failed: {e}")
            return InsertError[FragmentGQLModel](
                _entity=None,
                msg=FRAGMENT_INSERT_EMBEDDING_FAILED.msg,
                code=FRAGMENT_INSERT_EMBEDDING_FAILED.code,
                location=FRAGMENT_INSERT_EMBEDDING_FAILED.location,
                _input=fragment
            )
        
        # Final validation: Ensure embedding was successfully generated
        # Without a valid vector, the fragment cannot be used for semantic search
        if fragment.vector is None:
            return InsertError[FragmentGQLModel](
                _entity=None,
                msg=FRAGMENT_INSERT_EMBEDDING_FAILED.msg,
                code=FRAGMENT_INSERT_EMBEDDING_FAILED.code,
                location=FRAGMENT_INSERT_EMBEDDING_FAILED.location,
                _input=fragment
            )
        
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
                    "administrátor",
                    "děkan",
                    "rektor"
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
        # Conditional embedding update: only regenerate vector if content changed
        # This avoids expensive re-computation when only metadata is updated
        if fragment.content is not strawberry.UNSET and fragment.content:
            try:
                # Regenerate embedding with same logic as insert
                vec = embeddings.transform(fragment.content)
                
                # Handle txtai's variable return format (same as insert logic)
                if isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], (list, tuple)):
                    vec = vec[0]
                    
                fragment.vector = [float(x) for x in vec] if vec is not None else None
                
            except Exception as e:
                # Log embedding update failure - this is non-fatal but important to track
                print(f"[Fragment Update] Embedding update failed: {e}")
                return UpdateError[FragmentGQLModel](
                    _entity=db_row,
                    msg=FRAGMENT_UPDATE_EMBEDDING_FAILED.msg,
                    code=FRAGMENT_UPDATE_EMBEDDING_FAILED.code,
                    location=FRAGMENT_UPDATE_EMBEDDING_FAILED.location,
                    _input=fragment
                )
            
            # Ensure embedding update was successful
            # If content was provided but embedding failed, this is a critical error
            if fragment.vector is None:
                return UpdateError[FragmentGQLModel](
                    _entity=db_row,
                    msg=FRAGMENT_UPDATE_EMBEDDING_FAILED.msg,
                    code=FRAGMENT_UPDATE_EMBEDDING_FAILED.code,
                    location=FRAGMENT_UPDATE_EMBEDDING_FAILED.location,
                    _input=fragment
                )
        
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
                    "administrátor",
                    "děkan",
                    "rektor"
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
        # NOTE: db_row is None is already handled by LoadDataExtension
        return await Delete[FragmentGQLModel].DoItSafeWay(info=info, entity=fragment)
    