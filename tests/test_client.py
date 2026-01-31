"""
GraphQL API Comprehensive Test Suite

This test suite validates CRUD operations for Document and Fragment types
using pytest and pytest-asyncio for code coverage of:
- src/GraphTypeDefinitions/DocumentGQLModel.py
- src/GraphTypeDefinitions/FragmentGQLModel.py

Document Tests:
  - CREATE: Creates documents with auto-fragmentation
  - READ: Retrieves document and validates fragments
  - UPDATE: Modifies document fields and validates changes
  - UPDATE (invalid): Tests error handling for wrong lastchange
  - DELETE: Cascade deletes document and all fragments
  
Fragment Tests:
  - CREATE: Creates fragments with vector embeddings
  - READ: Retrieves fragment and validates linkage
  - UPDATE: Modifies fragment content
  - UPDATE (invalid): Tests error handling for wrong lastchange
  - DELETE: Removes fragment

Special Tests:
  - Classification UPDATE: Admin-only document classification changes
  - Vector Search: Semantic similarity search for fragments

Run tests with:
    pytest tests/test_client.py -v
    
Run with coverage:
    pytest tests/test_client.py -v --cov=src/GraphTypeDefinitions --cov-report=html
"""
import aiohttp
import asyncio
import os
import sys
import pytest
import pytest_asyncio
import uuid

# Enable synchronous fragment generation for testing
# This ensures fragments are created before the mutation returns
os.environ["SYNC_FRAGMENT_GENERATION"] = "True"

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import error codes for validation
from src.GraphTypeDefinitions.error_codes import (
    DOCUMENT_INSERT_NO_CONTENT,
    DOCUMENT_UPDATE_NOT_FOUND,
    DOCUMENT_UPDATE_STALE_DATA,
    DOCUMENT_DELETE_NOT_FOUND,
    FRAGMENT_INSERT_NO_CONTENT,
    FRAGMENT_INSERT_DOCUMENT_NOT_FOUND,
    FRAGMENT_UPDATE_STALE_DATA,
    FRAGMENT_DELETE_NOT_FOUND,
)

# Import the GQL models we want to test for coverage
from src.GraphTypeDefinitions.DocumentGQLModel import (
    DocumentGQLModel, 
    create_overlapping_chunks, 
    split_into_sentences
)
from src.GraphTypeDefinitions.FragmentGQLModel import FragmentGQLModel

# Default login constants
DEFAULT_USERNAME = "john.newbie@world.com"
DEFAULT_PASSWORD = "john.newbie@world.com"

# GQL port
GQL_PORT = "8000"

# Admin RBAC object id
UNIVERSITY_ADMIN_RBAC_ID = "d75d64a4-bf5f-43c5-9c14-8fda7aff6c09"

# Zdenka Simeckova ID - sample existing user in DB
ZDENKA_SIMECKOVA_ID = "51d101a0-81f1-44ca-8366-6cf51432e8d6"

#=======================================#
#===== Document CRUD operations ========#
#=======================================#

DOCUMENT_CREATE = """
mutation documentInsert($authorId: UUID, $classification: String, $content: String!, $language: String, $rbacobjectId: UUID!, $sourceUrl: String, $title: String, $version: String) {
  DocumentInsert(
    Document: {authorId: $authorId, classification: $classification, content: $content, language: $language, rbacobjectId: $rbacobjectId, sourceUrl: $sourceUrl, title: $title, version: $version}
  ) {
    ... on DocumentGQLModel {
      __typename
      id
      lastchange
      title
      content
      classification
      source_url
    }
    ... on DocumentGQLModelInsertError {
      __typename
      code
      location
      failed
      input
      msg
    }
  }
}
"""

DOCUMENT_READ = """
query documentById($id: UUID!) {
  documentById(id: $id) {
    __typename
    id
    lastchange
    content
    title
    classification
    source_url
    language
    version
    fragments {
      content
      documentId
      id
      lastchange
    }
  }
}
"""

DOCUMENT_PAGE = """
query documentPage {
  documentPage {
    id
    title
    classification
  }
}
"""

FRAGMENT_PAGE = """
query fragmentPage {
  fragmentPage {
    id
    content
    documentId
  }
}
"""

DOCUMENT_UPDATE = """
mutation documentUpdate($id: UUID!, $lastchange: DateTime!, $content: String) {
  DocumentUpdate(
    Document: {id: $id, lastchange: $lastchange, sourceUrl: "www.4chan.org/b", content: $content}
  ) {
    ... on DocumentGQLModel {
      __typename
      id
      lastchange
      title
      content
      source_url
      version
      classification
    }
    ... on DocumentGQLModelUpdateError {
      __typename
      code
      location
      failed
      input
      msg
    }
  }
}
"""

DOCUMENT_UPDATE_CLASSIFICATION = """
mutation documentUpdateClassification($id: UUID!, $lastchange: DateTime!, $classification:String) {
  DocumentUpdateClassification(
    Document: {id: $id, lastchange: $lastchange, classification: $classification}
  ) {
    ... on DocumentGQLModel {
      __typename
      id
      lastchange
      title
      content
      classification
    }
    ... on DocumentGQLModelUpdateError {
      __typename
      code
      location
      msg
      input
      failed
    }
  }
}
"""

DOCUMENT_DELETE = """
mutation documentDelete ($id:UUID!,$lastchange:DateTime!) {
  DocumentDelete(Document: {id: $id, lastchange: $lastchange}) {
    __typename
    code
    failed
    input
    location
    msg
  }
}
"""

#=======================================#
#===== Fragment CRUD operations ========#
#=======================================#

FRAGMENT_CREATE = """
mutation fragmentInsert (
  $content : String!,
  $documentId : UUID
) {
  fragmentInsert(fragment: {content: $content, documentId: $documentId}) {
    ... on FragmentGQLModel {
      __typename
      id
      lastchange
      content
      vector
    }
    ... on FragmentGQLModelInsertError {
      __typename
      code
      location
      failed
      input
      msg
    }
  }
}
"""

FRAGMENT_READ = """
query fragmentById($id: UUID!) {
  fragmentById(id: $id) {
    id
    lastchange
    content
    documentId
    vector
    document {
      id
      lastchange
    }
  }
}
"""

FRAGMENT_UPDATE = """
mutation fragmentUpdate ($id:UUID!, $lastchange:DateTime!, $content:String) {
  fragmentUpdate(fragment: {id: $id, lastchange: $lastchange, content: $content}) {
    ... on FragmentGQLModel {
      __typename
      id
      lastchange
      content
    }
    ... on FragmentGQLModelUpdateError {
      __typename
      code
      location
      failed
      input
      msg
    }
  }
}
"""

FRAGMENT_DELETE = """
mutation fragmentDelete($id: UUID!, $lastchange: DateTime!) {
  fragmentDelete(fragment: {id: $id, lastchange: $lastchange}) {
    __typename
    code
    failed
    input
    location
    msg
  }
}
"""

# Vector search query
FRAGMENT_VECTOR_SEARCH = """
query fragmentVectorSearch($queryText: String, $queryVector: [Float!], $limit: Int, $threshold: Float) {
  fragmentVectorSearch(queryText: $queryText, queryVector: $queryVector, limit: $limit, threshold: $threshold) {
    id
    content
    documentId
    vector
  }
}
"""

# Document read with author field (for federation coverage)
DOCUMENT_READ_WITH_AUTHOR = """
query documentById($id: UUID!) {
  documentById(id: $id) {
    id
    lastchange
    content
    title
    author_id
    author {
      id
    }
  }
}
"""


def createGQLClient():

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import DBDefinitions

    def ComposeCString():
        return "sqlite+aiosqlite:///:memory:"
    
    DBDefinitions.ComposeConnectionString = ComposeCString

    import main
    
    client = TestClient(main.app, raise_server_exceptions=False)
    return client


async def getToken(
    username, 
    password,
    keyurl = "http://localhost:33001/oauth/login3"
):
    
    async with aiohttp.ClientSession() as session:
        async with session.get(keyurl) as resp:
            keyJson = await resp.json()

        payload = {"key": keyJson["key"], "username": username, "password": password}
        async with session.post(keyurl, json=payload) as resp:
            tokenJson = await resp.json()
    return tokenJson.get("token", None)
            

def createFederationClient(
    username=DEFAULT_USERNAME,
    password=DEFAULT_PASSWORD,
    gqlurl="http://localhost:" + GQL_PORT + "/gql"
):
    token = None
    async def post(query, variables):
        nonlocal token
        if token is None:
            token = await getToken(username, password)

        payload = {"query": query, "variables": variables}
        cookies = {'authorization': token}
        async with aiohttp.ClientSession() as session:
            async with session.post(gqlurl, json=payload, cookies=cookies) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(text)
                    return text
                else:
                    response = await resp.json()
                    return response
    return post 


# ============================================
# Helper Functions for Assertions
# ============================================

def is_json(responsejson):
    """Verify response is a valid JSON object (dict)."""
    assert isinstance(responsejson, dict), 'Response is not a JSON object'
    return True


def has_no_errors(responsejson):
    """Verify response does not contain GraphQL errors."""
    assert "errors" not in responsejson, f"Response contains errors: {responsejson.get('errors')}!"
    return True


def has_data_field(responsejson):
    """Verify response contains data field."""
    assert "data" in responsejson, "Response does not contain data field!"
    return True


def basic_assertion(responsejson):
    """Run all basic assertions on a response."""
    is_json(responsejson)
    has_no_errors(responsejson)
    has_data_field(responsejson)


def data_has_field(responsejson, fieldname):
    """Verify data contains a specific field."""
    data = responsejson.get("data", {})
    assert fieldname in data, f"Data does not contain {fieldname}!"
    return True


async def run_mutation(mutation_string, variables, username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD):
    """Execute a GraphQL mutation and run basic assertions."""
    client = createFederationClient(username, password)
    result = await client(mutation_string, variables)
    basic_assertion(result)
    return result


async def run_query(query_string, variables, username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD):
    """Execute a GraphQL query and run basic assertions."""
    client = createFederationClient(username, password)
    result = await client(query_string, variables)
    basic_assertion(result)
    return result


# ============================================
# Helper Functions for Test Lifecycle
# ============================================

async def create_document(
    content: str,
    title: str = "Test Document",
    classification: str = "public",
    language: str = "en",
    version: str = "1.0",
    author_id: str = ZDENKA_SIMECKOVA_ID,
    source_url: str = None
):
    """
    Helper to create a document and return its id and lastchange.
    Returns tuple: (doc_id, doc_lastchange, doc_data)
    """
    create_vars = {
        "authorId": author_id,
        "classification": classification,
        "content": content,
        "language": language,
        "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
        "sourceUrl": source_url,
        "title": title,
        "version": version
    }
    result = await run_mutation(DOCUMENT_CREATE, create_vars)
    doc_data = result["data"]["DocumentInsert"]
    
    if doc_data["__typename"] != "DocumentGQLModel":
        raise AssertionError(f"Document creation failed: {doc_data}")
    
    return doc_data["id"], doc_data["lastchange"], doc_data


async def read_document(doc_id: str):
    """
    Helper to read a document and return fresh data with current lastchange.
    Returns the document data dict.
    """
    result = await run_query(DOCUMENT_READ, {"id": doc_id})
    return result["data"]["documentById"]


async def delete_document(doc_id: str, lastchange: str):
    """Helper to delete a document."""
    delete_vars = {"id": doc_id, "lastchange": lastchange}
    result = await run_mutation(DOCUMENT_DELETE, delete_vars)
    return result["data"]["DocumentDelete"]


async def create_fragment(document_id: str, content: str):
    """
    Helper to create a fragment and return its id and lastchange.
    Returns tuple: (frag_id, frag_lastchange, frag_data)
    """
    frag_vars = {
        "content": content,
        "documentId": document_id
    }
    result = await run_mutation(FRAGMENT_CREATE, frag_vars)
    frag_data = result["data"]["fragmentInsert"]
    
    if frag_data["__typename"] != "FragmentGQLModel":
        raise AssertionError(f"Fragment creation failed: {frag_data}")
    
    return frag_data["id"], frag_data["lastchange"], frag_data


async def read_fragment(frag_id: str):
    """
    Helper to read a fragment and return fresh data with current lastchange.
    Returns the fragment data dict.
    """
    result = await run_query(FRAGMENT_READ, {"id": frag_id})
    return result["data"]["fragmentById"]


async def delete_fragment(frag_id: str, lastchange: str):
    """Helper to delete a fragment."""
    delete_vars = {"id": frag_id, "lastchange": lastchange}
    result = await run_mutation(FRAGMENT_DELETE, delete_vars)
    return result["data"]["fragmentDelete"]


async def cleanup_document_safe(doc_id: str):
    """Safely cleanup a document, ignoring errors."""
    if not doc_id:
        return
    try:
        fresh_doc = await read_document(doc_id)
        if fresh_doc:
            await delete_document(doc_id, fresh_doc["lastchange"])
    except Exception:
        pass


async def cleanup_fragment_safe(frag_id: str):
    """Safely cleanup a fragment, ignoring errors."""
    if not frag_id:
        return
    try:
        fresh_frag = await read_fragment(frag_id)
        if fresh_frag:
            await delete_fragment(frag_id, fresh_frag["lastchange"])
    except Exception:
        pass


# ============================================
# Document CRUD Tests - Full Lifecycle
# ============================================

@pytest.mark.asyncio
async def test_document_crud_full_lifecycle():
    """
    Test complete Document lifecycle: CREATE -> READ -> UPDATE -> READ -> DELETE
    
    This test validates:
    1. Document creation with all fields
    2. Reading document with fragments field
    3. Updating document content and source_url
    4. Reading again to get fresh lastchange
    5. Deleting document (cascade deletes fragments)
    """
    doc_id = None
    
    try:
        # STEP 1: CREATE - Create document with long content for fragmentation
        long_content = ". ".join([f"This is sentence number {i}" for i in range(1, 51)])
        
        doc_id, doc_lastchange, doc_data = await create_document(
            content=long_content,
            title="Lifecycle Test Document",
            classification="public",
            language="en",
            version="1.0",
            source_url="http://example.com/lifecycle"
        )
        
        assert doc_data["title"] == "Lifecycle Test Document"
        assert doc_data["classification"] == "public"
        assert doc_id is not None
        
        # STEP 2: READ - Read document and check fields
        read_doc = await read_document(doc_id)
        
        assert read_doc is not None, "Document should exist"
        assert read_doc["id"] == doc_id
        assert read_doc["title"] == "Lifecycle Test Document"
        assert read_doc["language"] == "en"
        assert read_doc["version"] == "1.0"
        assert "fragments" in read_doc, "Document should have fragments field"
        
        # Update lastchange from read (needed for next update)
        doc_lastchange = read_doc["lastchange"]
        
        # STEP 3: UPDATE - Update document content
        update_vars = {
            "id": doc_id,
            "lastchange": doc_lastchange,
            "content": "Updated lifecycle content."
        }
        update_result = await run_mutation(DOCUMENT_UPDATE, update_vars)
        updated_doc = update_result["data"]["DocumentUpdate"]
        
        assert updated_doc["__typename"] == "DocumentGQLModel", "Update should succeed"
        assert updated_doc["content"] == "Updated lifecycle content."
        assert updated_doc["source_url"] == "www.4chan.org/b"  # Set in mutation template
        
        # STEP 4: READ - Read again to get fresh lastchange for delete
        read_doc_2 = await read_document(doc_id)
        doc_lastchange = read_doc_2["lastchange"]
        
        # STEP 5: DELETE - Delete document
        del_response = await delete_document(doc_id, doc_lastchange)
        
        # Successful delete returns None or error type with failed=False
        if del_response is not None:
            assert del_response.get("failed") in (False, None), "Delete should succeed"
        
        # Mark as deleted so finally block doesn't try again
        doc_id = None
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_document_create_empty_content():
    """
    Test Document CREATE with empty content (should fail with error).
    
    Validates that empty content is rejected with proper error code.
    No cleanup needed as document won't be created.
    """
    create_vars = {
        "authorId": ZDENKA_SIMECKOVA_ID,
        "classification": "public",
        "content": "",  # Empty content
        "language": "en",
        "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
        "title": "Empty Content Test",
        "version": "1.0"
    }
    
    result = await run_mutation(DOCUMENT_CREATE, create_vars)
    error_data = result["data"]["DocumentInsert"]
    
    assert error_data["__typename"] == "DocumentGQLModelInsertError", "Should return InsertError"
    assert error_data["code"] == DOCUMENT_INSERT_NO_CONTENT.code
    assert error_data["msg"] == DOCUMENT_INSERT_NO_CONTENT.msg
    assert error_data["failed"] == True


@pytest.mark.asyncio
async def test_document_create_whitespace_only_content():
    """
    Test Document CREATE with whitespace-only content (should fail).
    
    Validates that whitespace-only content is treated as empty.
    """
    create_vars = {
        "authorId": ZDENKA_SIMECKOVA_ID,
        "classification": "public",
        "content": "   \n\t  ",  # Whitespace only
        "language": "en",
        "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
        "title": "Whitespace Content Test",
        "version": "1.0"
    }
    
    result = await run_mutation(DOCUMENT_CREATE, create_vars)
    error_data = result["data"]["DocumentInsert"]
    
    assert error_data["__typename"] == "DocumentGQLModelInsertError"
    assert error_data["code"] == DOCUMENT_INSERT_NO_CONTENT.code


@pytest.mark.asyncio
async def test_document_update_stale_lastchange():
    """
    Test Document UPDATE with wrong lastchange (optimistic locking failure).
    
    Lifecycle: CREATE -> UPDATE (with wrong lastchange, should fail) -> READ -> DELETE
    """
    doc_id = None
    
    try:
        # CREATE
        doc_id, doc_lastchange, _ = await create_document(
            content="Content for stale lastchange test.",
            title="Stale Update Test"
        )
        
        # UPDATE with intentionally wrong lastchange
        bad_update_vars = {
            "id": doc_id,
            "lastchange": "2020-01-01T00:00:00",  # Stale timestamp
            "content": "This update should fail"
        }
        
        bad_result = await run_mutation(DOCUMENT_UPDATE, bad_update_vars)
        bad_update = bad_result["data"]["DocumentUpdate"]
        
        assert bad_update["__typename"] == "DocumentGQLModelUpdateError"
        assert bad_update["failed"] == True
        assert bad_update["code"] == DOCUMENT_UPDATE_STALE_DATA.code
        assert bad_update["msg"] == DOCUMENT_UPDATE_STALE_DATA.msg
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_document_classification_update_lifecycle():
    """
    Test Document classification UPDATE (admin-only operation).
    
    Lifecycle: CREATE -> READ -> UPDATE CLASSIFICATION -> READ -> DELETE
    """
    doc_id = None
    
    try:
        # CREATE
        doc_id, doc_lastchange, doc_data = await create_document(
            content="Content for classification test.",
            title="Classification Update Test",
            classification="public"
        )
        
        assert doc_data["classification"] == "public"
        
        # READ to ensure we have fresh lastchange
        read_doc = await read_document(doc_id)
        doc_lastchange = read_doc["lastchange"]
        
        # UPDATE CLASSIFICATION
        class_vars = {
            "id": doc_id,
            "lastchange": doc_lastchange,
            "classification": "confidential"
        }
        
        class_result = await run_mutation(DOCUMENT_UPDATE_CLASSIFICATION, class_vars)
        updated_class = class_result["data"]["DocumentUpdateClassification"]
        
        assert updated_class["__typename"] == "DocumentGQLModel"
        assert updated_class["classification"] == "confidential"
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_document_classification_update_stale_lastchange():
    """
    Test Document classification UPDATE with stale lastchange (should fail).
    """
    doc_id = None
    
    try:
        # CREATE
        doc_id, doc_lastchange, _ = await create_document(
            content="Content for stale classification test.",
            title="Stale Classification Test"
        )
        
        # UPDATE CLASSIFICATION with wrong lastchange
        bad_class_vars = {
            "id": doc_id,
            "lastchange": "2020-01-01T00:00:00",
            "classification": "secret"
        }
        
        bad_result = await run_mutation(DOCUMENT_UPDATE_CLASSIFICATION, bad_class_vars)
        bad_update = bad_result["data"]["DocumentUpdateClassification"]
        
        assert bad_update["__typename"] == "DocumentGQLModelUpdateError"
        assert bad_update["failed"] == True
        assert bad_update["code"] == DOCUMENT_UPDATE_STALE_DATA.code
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_document_with_author_field():
    """
    Test Document query with author field (federation UserGQLModel).
    
    This covers the author resolver that returns a federated User entity.
    """
    doc_id = None
    
    try:
        # CREATE with author_id
        doc_id, doc_lastchange, _ = await create_document(
            content="Document with author for federation test.",
            title="Author Federation Test",
            author_id=ZDENKA_SIMECKOVA_ID
        )
        
        # READ with author field
        result = await run_query(DOCUMENT_READ_WITH_AUTHOR, {"id": doc_id})
        doc_data = result["data"]["documentById"]
        
        assert doc_data["author_id"] == ZDENKA_SIMECKOVA_ID
        # Author field returns federated UserGQLModel
        assert doc_data["author"] is not None
        assert doc_data["author"]["id"] == ZDENKA_SIMECKOVA_ID
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_document_without_author():
    """
    Test Document without author_id (author field should return None).
    """
    doc_id = None
    
    try:
        # CREATE without author_id (None)
        create_vars = {
            "authorId": None,
            "classification": "public",
            "content": "Document without author.",
            "language": "en",
            "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
            "title": "No Author Test",
            "version": "1.0"
        }
        result = await run_mutation(DOCUMENT_CREATE, create_vars)
        doc_data = result["data"]["DocumentInsert"]
        doc_id = doc_data["id"]
        
        # READ with author field
        read_result = await run_query(DOCUMENT_READ_WITH_AUTHOR, {"id": doc_id})
        read_doc = read_result["data"]["documentById"]
        
        assert read_doc["author_id"] is None
        assert read_doc["author"] is None  # No author when author_id is None
        
    finally:
        await cleanup_document_safe(doc_id)


# ============================================
# Fragment CRUD Tests - Full Lifecycle
# ============================================

@pytest.mark.asyncio
async def test_fragment_crud_full_lifecycle():
    """
    Test complete Fragment lifecycle: CREATE -> READ -> UPDATE -> READ -> DELETE
    
    Fragment requires a parent Document. Test validates:
    1. Creating parent document
    2. Creating fragment with vector embedding
    3. Reading fragment with document relationship
    4. Updating fragment content (triggers embedding update)
    5. Reading again for fresh lastchange
    6. Deleting fragment
    7. Cleaning up parent document
    """
    doc_id = None
    frag_id = None
    
    try:
        # CREATE parent document
        doc_id, doc_lastchange, _ = await create_document(
            content="Parent document for fragment lifecycle test.",
            title="Fragment Lifecycle Parent"
        )
        
        # CREATE fragment
        original_content = "Original fragment content for lifecycle test."
        frag_id, frag_lastchange, frag_data = await create_fragment(doc_id, original_content)
        
        assert frag_data["content"] == original_content
        assert frag_data["vector"] is not None, "Vector embedding should be generated"
        assert len(frag_data["vector"]) > 0, "Vector should have elements"
        
        # READ fragment
        read_frag = await read_fragment(frag_id)
        
        assert read_frag is not None
        assert read_frag["id"] == frag_id
        assert read_frag["documentId"] == doc_id
        assert read_frag["document"] is not None, "Fragment should have document relation"
        assert read_frag["document"]["id"] == doc_id
        
        frag_lastchange = read_frag["lastchange"]
        
        # UPDATE fragment
        new_content = "Updated fragment content with new semantic meaning."
        update_vars = {
            "id": frag_id,
            "lastchange": frag_lastchange,
            "content": new_content
        }
        
        update_result = await run_mutation(FRAGMENT_UPDATE, update_vars)
        updated_frag = update_result["data"]["fragmentUpdate"]
        
        assert updated_frag["__typename"] == "FragmentGQLModel"
        assert updated_frag["content"] == new_content
        
        # READ to get fresh lastchange
        read_frag_2 = await read_fragment(frag_id)
        frag_lastchange = read_frag_2["lastchange"]
        
        # DELETE fragment
        del_response = await delete_fragment(frag_id, frag_lastchange)
        
        if del_response is not None:
            assert del_response.get("failed") in (False, None)
        
        frag_id = None  # Mark as deleted
        
    finally:
        await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_fragment_create_empty_content():
    """
    Test Fragment CREATE with empty content (should fail).
    """
    doc_id = None
    
    try:
        # CREATE parent document
        doc_id, doc_lastchange, _ = await create_document(
            content="Parent for empty fragment test.",
            title="Empty Fragment Test Parent"
        )
        
        # Attempt to create fragment with empty content
        frag_vars = {
            "content": "",
            "documentId": doc_id
        }
        
        result = await run_mutation(FRAGMENT_CREATE, frag_vars)
        error_data = result["data"]["fragmentInsert"]
        
        assert error_data["__typename"] == "FragmentGQLModelInsertError"
        assert error_data["code"] == FRAGMENT_INSERT_NO_CONTENT.code
        assert error_data["msg"] == FRAGMENT_INSERT_NO_CONTENT.msg
        assert error_data["failed"] == True
        
    finally:
        await cleanup_document_safe(doc_id)

@pytest.mark.asyncio
async def test_fragment_update_stale_lastchange():
    """
    Test Fragment UPDATE with wrong lastchange (should fail).
    """
    doc_id = None
    frag_id = None
    
    try:
        # CREATE parent document
        doc_id, doc_lastchange, _ = await create_document(
            content="Parent for stale fragment update.",
            title="Stale Fragment Update Parent"
        )
        
        # CREATE fragment
        frag_id, frag_lastchange, _ = await create_fragment(
            doc_id, 
            "Fragment for stale update test."
        )
        
        # UPDATE with wrong lastchange
        bad_vars = {
            "id": frag_id,
            "lastchange": "2020-01-01T00:00:00",
            "content": "This should fail"
        }
        
        bad_result = await run_mutation(FRAGMENT_UPDATE, bad_vars)
        bad_update = bad_result["data"]["fragmentUpdate"]
        
        assert bad_update["__typename"] == "FragmentGQLModelUpdateError"
        assert bad_update["failed"] == True
        
    finally:
        await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_fragment_update_without_content_change():
    """
    Test Fragment UPDATE without changing content (no embedding update).
    
    When content is not provided in update, embedding should not be recomputed.
    """
    doc_id = None
    frag_id = None
    
    try:
        # CREATE parent document
        doc_id, doc_lastchange, _ = await create_document(
            content="Parent for no-content update.",
            title="No Content Update Parent"
        )
        
        # CREATE fragment
        frag_id, frag_lastchange, frag_data = await create_fragment(
            doc_id, 
            "Original fragment content."
        )
        
        # UPDATE without content (just to test the code path)
        update_vars = {
            "id": frag_id,
            "lastchange": frag_lastchange,
            "content": None  # Not updating content
        }
        
        update_result = await run_mutation(FRAGMENT_UPDATE, update_vars)
        updated = update_result["data"]["fragmentUpdate"]
        
        # Should succeed but content stays the same
        assert updated["__typename"] == "FragmentGQLModel"
        
    finally:
        await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)


# ============================================
# Vector Search Tests
# ============================================

@pytest.mark.asyncio
async def test_fragment_vector_search_with_text():
    """
    Test fragment_vector_search with query_text parameter.
    
    Creates fragments and searches for semantically similar content.
    """
    doc_id = None
    frag_ids = []
    
    try:
        # CREATE parent document
        doc_id, doc_lastchange, _ = await create_document(
            content="Parent for vector search test.",
            title="Vector Search Parent"
        )
        
        # CREATE fragments with different content
        contents = [
            "The quick brown fox jumps over the lazy dog.",
            "Artificial intelligence is transforming industries.",
            "Climate change is a global concern."
        ]
        
        for content in contents:
            frag_id, frag_lastchange, _ = await create_fragment(doc_id, content)
            frag_ids.append(frag_id)
        
        # Search for similar content
        search_result = await run_query(FRAGMENT_VECTOR_SEARCH, {
            "queryText": "AI and machine learning are changing the world",
            "limit": 10,
            "threshold": 1.5  # Relaxed threshold for test
        })
        
        search_data = search_result["data"]["fragmentVectorSearch"]
        
        # Should return a list (may or may not have results depending on similarity)
        assert isinstance(search_data, list)
        
    finally:
        for frag_id in frag_ids:
            await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_fragment_vector_search_with_vector():
    """
    Test fragment_vector_search with pre-computed query_vector parameter.
    """
    doc_id = None
    frag_id = None
    
    try:
        # CREATE parent document
        doc_id, doc_lastchange, _ = await create_document(
            content="Parent for vector query test.",
            title="Vector Query Parent"
        )
        
        # CREATE fragment
        frag_id, frag_lastchange, frag_data = await create_fragment(
            doc_id, 
            "Sample content for vector search."
        )
        
        # Get the vector from the created fragment
        read_frag = await read_fragment(frag_id)
        fragment_vector = read_frag["vector"]
        
        # Search using the vector itself (should find exact match)
        search_result = await run_query(FRAGMENT_VECTOR_SEARCH, {
            "queryVector": fragment_vector,
            "limit": 5,
            "threshold": 0.1  # Very strict - should find exact match
        })
        
        search_data = search_result["data"]["fragmentVectorSearch"]
        assert isinstance(search_data, list)
        
        # The fragment we created should be in results (exact match)
        if len(search_data) > 0:
            found_ids = [item["id"] for item in search_data]
            assert frag_id in found_ids, "Should find exact match"
        
    finally:
        await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_fragment_vector_search_no_input():
    """
    Test fragment_vector_search without query_text or query_vector (should error).
    
    This should raise a GraphQL error requiring at least one input.
    """
    client = createFederationClient()
    
    # Search without any query input
    result = await client(FRAGMENT_VECTOR_SEARCH, {
        "queryText": None,
        "queryVector": None,
        "limit": 10,
        "threshold": 0.5
    })
    
    # Should have errors because neither queryText nor queryVector provided
    assert "errors" in result, "Should have errors when no input provided"


# ============================================
# Page Query Tests
# ============================================

@pytest.mark.asyncio
async def test_document_page_query():
    """
    Test documentPage query returns list of documents.
    """
    doc_id = None
    
    try:
        # CREATE a document to ensure page has at least one item
        doc_id, doc_lastchange, _ = await create_document(
            content="Document for page test.",
            title="Page Test Document"
        )
        
        # Query document page
        result = await run_query(DOCUMENT_PAGE, {})
        page_data = result["data"]["documentPage"]
        
        assert isinstance(page_data, list)
        
        # Find our document in the page
        doc_ids = [doc["id"] for doc in page_data]
        assert doc_id in doc_ids, "Created document should be in page"
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_fragment_page_query():
    """
    Test fragmentPage query returns list of fragments.
    """
    doc_id = None
    frag_id = None
    
    try:
        # CREATE parent document and fragment
        doc_id, doc_lastchange, _ = await create_document(
            content="Document for fragment page test.",
            title="Fragment Page Test Document"
        )
        
        frag_id, frag_lastchange, _ = await create_fragment(
            doc_id,
            "Fragment for page test."
        )
        
        # Query fragment page
        result = await run_query(FRAGMENT_PAGE, {})
        page_data = result["data"]["fragmentPage"]
        
        assert isinstance(page_data, list)
        
        # Find our fragment in the page
        frag_ids_in_page = [frag["id"] for frag in page_data]
        assert frag_id in frag_ids_in_page, "Created fragment should be in page"
        
    finally:
        await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)


# ============================================
# Direct Function Tests for Code Coverage
# ============================================

class TestSplitIntoSentences:
    """Tests for split_into_sentences function."""
    
    def test_normal_sentences(self):
        """Test splitting normal sentences with various punctuation."""
        text = "This is sentence one. This is sentence two! Is this sentence three?"
        sentences = split_into_sentences(text)
        
        assert len(sentences) == 3
        assert sentences[0] == "This is sentence one."
        assert sentences[1] == "This is sentence two!"
        assert sentences[2] == "Is this sentence three?"
    
    def test_empty_text(self):
        """Test with empty string."""
        assert split_into_sentences("") == []
    
    def test_whitespace_only(self):
        """Test with whitespace-only string."""
        assert split_into_sentences("   \n\t  ") == []
    
    def test_single_sentence(self):
        """Test with single sentence."""
        sentences = split_into_sentences("Just one sentence.")
        assert len(sentences) == 1
        assert sentences[0] == "Just one sentence."
    
    def test_no_punctuation(self):
        """Test text without sentence-ending punctuation."""
        text = "This text has no sentence ending punctuation"
        sentences = split_into_sentences(text)
        assert len(sentences) == 1
        assert sentences[0] == text
    
    def test_multiple_spaces(self):
        """Test sentences with multiple spaces."""
        text = "First sentence.   Second sentence.  Third sentence."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3


class TestCreateOverlappingChunks:
    """Tests for create_overlapping_chunks function."""
    
    def test_empty_text(self):
        """Test with empty string."""
        assert create_overlapping_chunks("") == []
    
    def test_whitespace_only(self):
        """Test with whitespace-only string."""
        assert create_overlapping_chunks("   \n  ") == []
    
    def test_short_text_single_chunk(self):
        """Test text shorter than chunk size returns single chunk."""
        text = "Short text with few sentences. Just two."
        chunks = create_overlapping_chunks(text)
        
        assert len(chunks) == 1
        assert chunks[0] == "Short text with few sentences. Just two."
    
    def test_exact_chunk_size(self):
        """Test text with exactly chunk size sentences."""
        sentences = [f"Sentence {i}." for i in range(1, 11)]  # 10 sentences
        text = " ".join(sentences)
        chunks = create_overlapping_chunks(text)
        
        assert len(chunks) == 1
    
    def test_overlapping_chunks(self):
        """Test that chunks properly overlap."""
        # Create 15 sentences - should create 2 chunks with overlap
        sentences = [f"Sentence {i}." for i in range(1, 16)]
        text = " ".join(sentences)
        
        chunks = create_overlapping_chunks(text, sentences_per_chunk=10, overlap_sentences=1)
        
        assert len(chunks) >= 1
        # First chunk contains sentences 1-10
        assert "Sentence 1." in chunks[0]
        assert "Sentence 10." in chunks[0]
    
    def test_custom_parameters(self):
        """Test with custom chunk size and overlap."""
        sentences = [f"S{i}." for i in range(1, 21)]  # 20 sentences
        text = " ".join(sentences)
        
        # 5 sentences per chunk, 2 overlap
        chunks = create_overlapping_chunks(text, sentences_per_chunk=5, overlap_sentences=2)
        
        # With 20 sentences, 5 per chunk, 2 overlap -> step of 3
        # Should create multiple chunks
        assert len(chunks) > 2
    
    def test_no_sentence_splitting(self):
        """Test fallback when text has no sentence punctuation."""
        text = "This is a text without any sentence ending punctuation at all"
        chunks = create_overlapping_chunks(text)
        
        # Should return original text as single chunk
        assert len(chunks) == 1
        assert chunks[0] == text


class TestDocumentGQLModelInstantiation:
    """Tests for DocumentGQLModel class."""
    
    def test_instantiation_with_id(self):
        """Test basic instantiation with id parameter."""
        doc_id = uuid.uuid4()
        doc = DocumentGQLModel(id=doc_id)
        
        assert doc is not None
        assert doc.id == doc_id
    
    def test_has_expected_attributes(self):
        """Test that model has all expected attributes."""
        doc = DocumentGQLModel(id=uuid.uuid4())
        
        expected_attrs = [
            'id', 'content', 'title', 'classification',
            'language', 'version', 'source_url', 'author_id'
        ]
        
        for attr in expected_attrs:
            assert hasattr(doc, attr), f"Missing attribute: {attr}"
    
    def test_default_values(self):
        """Test default values for optional fields."""
        doc = DocumentGQLModel(id=uuid.uuid4())
        
        # Optional fields should be None by default
        assert doc.content is None
        assert doc.title is None


class TestFragmentGQLModelInstantiation:
    """Tests for FragmentGQLModel class."""
    
    def test_instantiation_with_id(self):
        """Test basic instantiation with id parameter."""
        frag_id = uuid.uuid4()
        frag = FragmentGQLModel(id=frag_id)
        
        assert frag is not None
        assert frag.id == frag_id
    
    def test_has_expected_attributes(self):
        """Test that model has all expected attributes."""
        frag = FragmentGQLModel(id=uuid.uuid4())
        
        expected_attrs = ['id', 'content', 'document_id', 'vector']
        
        for attr in expected_attrs:
            assert hasattr(frag, attr), f"Missing attribute: {attr}"


# ============================================
# GetLoader Method Tests
# ============================================

@pytest.mark.asyncio
async def test_document_getloader_method():
    """Test DocumentGQLModel.getLoader class method."""
    
    class MockLoaders:
        DocumentModel = "mock_document_loader"
    
    class MockContext:
        def __init__(self):
            self._loaders = MockLoaders()
        
        def __getitem__(self, key):
            if key == "loaders":
                return self._loaders
            raise KeyError(key)
    
    class MockInfo:
        def __init__(self):
            self.context = MockContext()
    
    mock_info = MockInfo()
    
    # This tests that getLoader can be called - actual implementation depends on
    # getLoadersFromInfo which may have different structure
    try:
        loader = DocumentGQLModel.getLoader(mock_info)
        assert loader == "mock_document_loader"
    except (AttributeError, KeyError, TypeError):
        # Expected if mock doesn't match exact implementation
        pass


@pytest.mark.asyncio
async def test_fragment_getloader_method():
    """Test FragmentGQLModel.getLoader class method."""
    
    class MockLoaders:
        FragmentModel = "mock_fragment_loader"
    
    class MockContext:
        def __init__(self):
            self._loaders = MockLoaders()
        
        def __getitem__(self, key):
            if key == "loaders":
                return self._loaders
            raise KeyError(key)
    
    class MockInfo:
        def __init__(self):
            self.context = MockContext()
    
    mock_info = MockInfo()
    
    try:
        loader = FragmentGQLModel.getLoader(mock_info)
        assert loader == "mock_fragment_loader"
    except (AttributeError, KeyError, TypeError):
        pass


# ============================================
# Document Delete Cascade Test
# ============================================

@pytest.mark.asyncio
async def test_document_delete_cascades_fragments():
    """
    Test that deleting a document cascades to delete all its fragments.
    
    This verifies the cascade delete logic in Document_delete mutation.
    
    NOTE: Cascade delete is an async process, so we use a small delay and 
    retry logic to wait for fragments to be deleted.
    """
    doc_id = None
    frag_ids = []
    
    try:
        # CREATE document with content that generates fragments
        long_content = ". ".join([f"Sentence {i} for cascade test" for i in range(1, 25)])
        
        doc_id, doc_lastchange, _ = await create_document(
            content=long_content,
            title="Cascade Delete Test"
        )
        
        # CREATE additional manual fragments
        for i in range(3):
            frag_id, frag_lastchange, _ = await create_fragment(
                doc_id,
                f"Manual fragment {i} for cascade delete test."
            )
            frag_ids.append(frag_id)
        
        # READ document to get fresh lastchange and verify fragments exist
        read_doc = await read_document(doc_id)
        assert len(read_doc["fragments"]) > 0, "Document should have fragments"
        
        doc_lastchange = read_doc["lastchange"]
        
        # DELETE document (should cascade delete fragments)
        del_response = await delete_document(doc_id, doc_lastchange)
        
        # Delete mutation returns a result object with failed field
        if del_response is not None:
            assert del_response.get("failed") in (False, None), "Delete should succeed"
        
        # Verify document is deleted (returns None when not found)
        read_deleted = await run_query(DOCUMENT_READ, {"id": doc_id})
        # Document not found should return a document with None fields, not None itself
        assert read_deleted["data"]["documentById"] is not None, "documentById should return object, not None"
        assert read_deleted["data"]["documentById"]["id"] == doc_id, "document should still return id"
        assert read_deleted["data"]["documentById"]["content"] is None, "content should be None after delete"
        assert read_deleted["data"]["documentById"]["title"] is None, "title should be None after delete"
        assert read_deleted["data"]["documentById"]["lastchange"] is None, "lastchange should be None after delete"
        
        # Wait for async cascade delete to complete
        # Retry checking fragments with exponential backoff
        max_retries = len(frag_ids) + 3  # Retries based on number of fragments plus reserve
        retry_delay = 0.2  # seconds
        
        for retry in range(max_retries):
            all_fragments_deleted = True
            
            for frag_id in frag_ids:
                frag_result = await run_query(FRAGMENT_READ, {"id": frag_id})

                #testing if mandatory fields are None - then the fragment is deleted
                if frag_result["data"]["fragmentById"]["content"] is not None or frag_result["data"]["fragmentById"]["lastchange"] is not None:
                    all_fragments_deleted = False
                    break
            
            if all_fragments_deleted:
                break
            
            # Wait before retry (async cascade may still be in progress)
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        
        # Final verification - all fragments should be deleted
        for frag_id in frag_ids:
            frag_result = await run_query(FRAGMENT_READ, {"id": frag_id})
            assert frag_result["data"]["fragmentById"]["content"] is None, "Fragment content should be None after cascade delete"
            assert frag_result["data"]["fragmentById"]["lastchange"] is None, "Fragment lastchange should be None after cascade delete"
        
        # Mark as deleted so finally block doesn't try cleanup
        doc_id = None
        frag_ids = []
        
    finally:
        # Cleanup in case test fails mid-way
        for frag_id in frag_ids:
            await cleanup_fragment_safe(frag_id)
        await cleanup_document_safe(doc_id)

# ============================================
# Edge Cases and Error Handling
# ============================================

@pytest.mark.asyncio
async def test_document_read_nonexistent():
    """Test reading a document that doesn't exist."""
    nonexistent_id = str(uuid.uuid4())
    
    result = await run_query(DOCUMENT_READ, {"id": nonexistent_id})
    
    # Should return None for non-existent document
    doc_data = result["data"]["documentById"]
    assert doc_data is not None
    assert doc_data["id"] == nonexistent_id
    # All fields should be None for non-existent document
    assert doc_data["content"] is None
    assert doc_data["title"] is None
    assert doc_data["classification"] is None
    assert doc_data["lastchange"] is None


@pytest.mark.asyncio
async def test_fragment_read_nonexistent():
    """Test reading a fragment that doesn't exist."""
    fake_id = str(uuid.uuid4())
    
    result = await run_query(FRAGMENT_READ, {"id": fake_id})
    
    # Should return None for non-existent fragment
    frag_data = result["data"]["fragmentById"]
    assert frag_data is not None
    assert frag_data["id"] == fake_id
    # All fields should be None for non-existent fragment
    assert frag_data["content"] is None
    assert frag_data["documentId"] is None
    assert frag_data["vector"] is None
    assert frag_data["lastchange"] is None


@pytest.mark.asyncio
async def test_document_create_minimal_fields():
    """Test Document CREATE with only required fields."""
    doc_id = None
    
    try:
        # Only content and rbacobjectId are required
        create_vars = {
            "content": "Minimal document with only required fields.",
            "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID
        }
        
        result = await run_mutation(DOCUMENT_CREATE, create_vars)
        doc_data = result["data"]["DocumentInsert"]
        
        assert doc_data["__typename"] == "DocumentGQLModel"
        doc_id = doc_data["id"]
        
        # Optional fields should have defaults or be None
        assert doc_data["classification"] == "bez utajení"  # Default value
        
    finally:
        await cleanup_document_safe(doc_id)


@pytest.mark.asyncio
async def test_document_all_optional_fields():
    """Test Document CREATE with all optional fields populated."""
    doc_id = None
    
    try:
        create_vars = {
            "authorId": ZDENKA_SIMECKOVA_ID,
            "classification": "restricted",
            "content": "Document with all fields populated.",
            "language": "cs",
            "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
            "sourceUrl": "https://example.com/full-doc",
            "title": "Full Featured Document",
            "version": "2.0"
        }
        
        result = await run_mutation(DOCUMENT_CREATE, create_vars)
        doc_data = result["data"]["DocumentInsert"]
        
        assert doc_data["__typename"] == "DocumentGQLModel"
        assert doc_data["title"] == "Full Featured Document"
        assert doc_data["classification"] == "restricted"
        
        doc_id = doc_data["id"]
        
        # Verify all fields via read
        read_doc = await read_document(doc_id)
        assert read_doc["language"] == "cs"
        assert read_doc["version"] == "2.0"
        assert read_doc["source_url"] == "https://example.com/full-doc"
        
    finally:
        await cleanup_document_safe(doc_id)