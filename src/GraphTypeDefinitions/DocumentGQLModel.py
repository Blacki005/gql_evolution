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

# Import error codes for consistent error handling
from .error_codes import (
    DOCUMENT_INSERT_NO_CONTENT,
    DOCUMENT_UPDATE_NOT_FOUND,
    DOCUMENT_UPDATE_STALE_DATA,
    DOCUMENT_DELETE_NOT_FOUND
)

FragmentGQLModel = typing.Annotated["FragmentGQLModel", strawberry.lazy(".FragmentGQLModel")]
FragmentInputFilter = typing.Annotated["FragmentInputFilter", strawberry.lazy(".FragmentGQLModel")]
UserGQLModel = typing.Annotated["UserGQLModel", strawberry.lazy(".UserGQLModel")]


# Helper function for text fragmentation
def split_into_sentences(text: str) -> typing.List[str]:
    """Split text into sentences using basic punctuation rules."""
    import re
    # Split on sentence-ending punctuation followed by space or end of string
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def create_overlapping_chunks(
    text: str, 
    sentences_per_chunk: int = 10, 
    overlap_sentences: int = 1
) -> typing.List[str]:
    """
    Split text into overlapping chunks based on sentence count.
    Much simpler than character-based chunking!
    
    Args:
        text: Text to split
        sentences_per_chunk: Number of sentences per chunk (default: 10)
        overlap_sentences: Number of sentences to overlap (default: 1)
    
    Returns:
        List of text chunks (each chunk is 10 sentences with 1 sentence overlap)
    
    Example:
        Sentences: [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12]
        Chunk 1: S1-S10
        Chunk 2: S10-S19  (S10 is the overlap)
        Chunk 3: S19-S28  (S19 is the overlap)
    """
    if not text or not text.strip():
        return []
    
    # Split text into sentences
    sentences = split_into_sentences(text)
    
    if not sentences:
        return [text]  # Fallback if no sentence splitting possible
    
    # If document has fewer sentences than chunk size, return as single chunk
    if len(sentences) <= sentences_per_chunk:
        return [' '.join(sentences)]
    
    chunks = []
    i = 0
    
    while i < len(sentences):
        # Take sentences_per_chunk sentences starting from position i
        chunk_sentences = sentences[i:i + sentences_per_chunk]
        
        if chunk_sentences:  # Only add non-empty chunks
            chunks.append(' '.join(chunk_sentences))
        
        # Move forward by (sentences_per_chunk - overlap_sentences)
        # This creates the overlap
        i += sentences_per_chunk - overlap_sentences
    
    return chunks


@createInputs2
class DocumentInputFilter:
    title: str
    content: str
    classification: str
    language: str
    version: str
    source_url: str
    author_id: IDType
    created: datetime.datetime
    lastchange: datetime.datetime
    id: IDType
    valid: bool
    fragments: FragmentInputFilter = strawberry.field(description="""Fragment filter operators, 
for field "fragments" the filters could be
{"fragments": {"content": {"_eq": "some text"}}}
{"fragments": {"document_id": {"_eq": "ce22d5ab-f867-4cf1-8e3c-ee77eab81c24"}}}
{"fragments": {"_and": [{"content": {"_ilike": "%keyword%"}}, {"valid": {"_eq": true}}]}}
""")


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
        default="bez utajení"
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


# Background task for generating document fragments with embeddings
async def generate_document_fragments(
    document_id: IDType,
    content: str,
    createdby_id: IDType,
    info: strawberry.types.Info
):
    """
    Background task to split document into fragments and generate embeddings.
    Runs asynchronously without blocking the document insert response.
    Uses direct database insertion with embedding computation.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from src.DBDefinitions import FragmentModel
    from txtai import Embeddings
    
    print(f"[Background Task] Starting fragment generation for document {document_id}")
    
    # Load embedding model in thread
    def compute_embedding(text: str) -> typing.List[float]:
        """Compute embedding in a separate thread (blocking operation)."""
        try:
            embeddings = Embeddings(path="/home/filip/all-MiniLM-L6-v2")
            vec = embeddings.transform(text)
            # Handle both single vector or list-of-vectors
            if isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], (list, tuple)):
                vec = vec[0]
            return [float(x) for x in vec] if vec is not None else None
        except Exception as e:
            print(f"[Background Task] Error computing embedding: {e}")
            return None
    
    try:
        # Split document into chunks (10 sentences per chunk, 1 sentence overlap)
        #its not possible that there are no chunks, because content is required field
        chunks = create_overlapping_chunks(content, sentences_per_chunk=10, overlap_sentences=1)        

        # Get database session
        loader = getLoadersFromInfo(info).FragmentModel
        session = loader.session
        
        # Use ThreadPoolExecutor for CPU-bound embedding computation
        executor = ThreadPoolExecutor(max_workers=1)
        
        expected_fragments = len(chunks)
        fragments_created = 0
        for idx, chunk_text in enumerate(chunks):
            # Yield control to event loop
            await asyncio.sleep(0)
                        
            # Compute embedding in separate thread (non-blocking)
            loop = asyncio.get_event_loop()
            vector = await loop.run_in_executor(executor, compute_embedding, chunk_text)
            
            if vector is None:
                continue
            
            # Create fragment directly in database
            import uuid as _uuid
            fragment = FragmentModel(
                id=_uuid.uuid4(),
                document_id=document_id,
                content=chunk_text,
                vector=vector,
                rbacobject_id=None,  # Fragments don't need separate RBAC, inherit from document
                createdby_id=createdby_id,
                changedby_id=createdby_id,
                created=datetime.datetime.now(),
                lastchange=datetime.datetime.now()
            )
            session.add(fragment)
            fragments_created += 1
            
            # Yield control after each fragment
            await asyncio.sleep(0)


        # Commit only if all fragments were created successfully
        if fragments_created == expected_fragments:
            await session.commit()
            print(f"[Background Task] Successfully created all {fragments_created} fragments for document {document_id}")
        else:
            await session.rollback()
            print(f"[Background Task] Rollback: Only {fragments_created}/{expected_fragments} fragments created for document {document_id}")
        executor.shutdown(wait=False)
        
    except Exception as e:
        # Log error but don't fail the document insert
        print(f"[Background Task] Error generating fragments for document {document_id}: {e}")
        import traceback
        traceback.print_exc()


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
        import asyncio
        import os
        from uoishelpers.resolvers import getUserFromInfo
        
        # Validace: Content nesmí být prázdný
        if not Document.content or not Document.content.strip():
            return InsertError[DocumentGQLModel](
                _entity=None,
                msg=DOCUMENT_INSERT_NO_CONTENT.msg,
                code=DOCUMENT_INSERT_NO_CONTENT.code,
                location=DOCUMENT_INSERT_NO_CONTENT.location,
                _input=Document
            )
        
        # Auto-generate ID if not provided
        if getattr(Document, "id", None) is None:
            import uuid as _uuid
            Document.id = _uuid.uuid4()
        
        # Get current user for createdby_id
        user = getUserFromInfo(info)
        createdby_id = user["id"]
        
        # Insert document first (must succeed before fragmenting)
        result = await Insert[DocumentGQLModel].DoItSafeWay(info=info, entity=Document)
        
        # If insert failed, return the error
        if isinstance(result, InsertError):
            return result
        
        # Generate fragments synchronously in test mode, asynchronously in production
        if Document.content and Document.content.strip():
            # Check if we're in test/sync mode
            sync_mode = os.getenv("SYNC_FRAGMENT_GENERATION", "False").lower() in ("true", "1", "yes")
            
            if sync_mode:
                # Synchronous mode: wait for fragments to be created (for tests)
                await generate_document_fragments(
                    document_id=Document.id,
                    content=Document.content,
                    createdby_id=createdby_id,
                    info=info
                )
            else:
                # Asynchronous mode: launch background task (for production)
                asyncio.create_task(
                    generate_document_fragments(
                        document_id=Document.id,
                        content=Document.content,
                        createdby_id=createdby_id,
                        info=info
                    )
                )
        
        return result
    

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
                    "administrátor",
                    "děkan",
                    "rektor"
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
        # Validace: Dokument musí existovat
        if db_row is None:
            return UpdateError[DocumentGQLModel](
                _entity=None,
                msg=DOCUMENT_UPDATE_NOT_FOUND.msg,
                code=DOCUMENT_UPDATE_NOT_FOUND.code,
                location=DOCUMENT_UPDATE_NOT_FOUND.location,
                _input=Document
            )
        
        # Validace: Kontrola lastchange (optimistic locking)
        if db_row.lastchange != Document.lastchange:
            return UpdateError[DocumentGQLModel](
                _entity=db_row,
                msg=DOCUMENT_UPDATE_STALE_DATA.msg,
                code=DOCUMENT_UPDATE_STALE_DATA.code,
                location=DOCUMENT_UPDATE_STALE_DATA.location,
                _input=Document
            )
        
        return await Update[DocumentGQLModel].DoItSafeWay(info=info, entity=Document)
    

    @strawberry.mutation(
        description="""Update Document classification (restricted to specific roles)""",
        permission_classes=[
            OnlyForAuthentized
        ],
        extensions=[
            UserAccessControlExtension[UpdateError, DocumentGQLModel](
                roles=[
                    "administrátor",  
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
        # Validace: Dokument musí existovat
        if db_row is None:
            return UpdateError[DocumentGQLModel](
                _entity=None,
                msg=DOCUMENT_UPDATE_NOT_FOUND.msg,
                code=DOCUMENT_UPDATE_NOT_FOUND.code,
                location=DOCUMENT_UPDATE_NOT_FOUND.location,
                _input=Document
            )
        
        # Validace: Kontrola lastchange (optimistic locking)
        if db_row.lastchange != Document.lastchange:
            return UpdateError[DocumentGQLModel](
                _entity=db_row,
                msg=DOCUMENT_UPDATE_STALE_DATA.msg,
                code=DOCUMENT_UPDATE_STALE_DATA.code,
                location=DOCUMENT_UPDATE_STALE_DATA.location,
                _input=Document
            )
        
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
                    "administrátor",
                    "děkan",
                    "rektor"
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
        # Validace: Dokument musí existovat
        if db_row is None:
            return DeleteError[DocumentGQLModel](
                _entity=None,
                msg=DOCUMENT_DELETE_NOT_FOUND.msg,
                code=DOCUMENT_DELETE_NOT_FOUND.code,
                location=DOCUMENT_DELETE_NOT_FOUND.location,
                _input=Document
            )
        
        # Cascade delete: delete all fragments associated with this document first
        from sqlalchemy import delete
        from src.DBDefinitions import FragmentModel
        
        loaders = getLoadersFromInfo(info)
        loader = loaders.FragmentModel
        session = loader.session
        
        # Delete all fragments with this document_id
        stmt = delete(FragmentModel).where(FragmentModel.document_id == Document.id)
        result = await session.execute(stmt)
        await session.commit()
        
        deleted_count = result.rowcount
        print(f"[Document Delete] Deleted {deleted_count} fragments for document {Document.id}")
        
        # Now delete the document itself
        return await Delete[DocumentGQLModel].DoItSafeWay(info=info, entity=Document)
    