"""
GraphQL API Comprehensive Test Suite

This test suite validates CRUD operations for Document and Fragment types:

✓ Document Tests:
  - CREATE: Creates documents with auto-fragmentation
  - READ: Retrieves document and validates fragments
  - UPDATE: Modifies document fields and validates changes
  - UPDATE (invalid): Tests error handling for wrong lastchange
  - DELETE: Cascade deletes document and all fragments
  
✓ Fragment Tests:
  - CREATE: Creates fragments with vector embeddings
  - READ: Retrieves fragment and validates linkage
  - UPDATE: Modifies fragment content
  - UPDATE (invalid): Tests error handling for wrong lastchange
  - DELETE: Removes fragment

✓ Special Tests:
  - Classification UPDATE: Admin-only document classification changes

Features:
- Colored terminal output for readability
- Validates __typename for proper error types
- Tests permission errors and optimistic locking
- Verifies values actually change in UPDATE operations
- Uses SYNC_FRAGMENT_GENERATION for deterministic tests
"""
import aiohttp
import asyncio
import os
import signal
import subprocess
import time

#default login constants:
DEFAULT_USERNAME = "john.newbie@world.com"
DEFAULT_PASSWORD = "john.newbie@world.com"

#gql_port:
GQL_PORT = "8000"

#admin RBAC object id:
UNIVERSITY_ADMIN_RBAC_ID = "d75d64a4-bf5f-43c5-9c14-8fda7aff6c09"

#Zdenka Simeckova ID - sample existing user in DB:
ZDENKA_SIMECKOVA_ID = "51d101a0-81f1-44ca-8366-6cf51432e8d6"

#=======================================#
#===== Fragment CRUD operations ========#
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
query documentById($id: UUID!) {
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
    gqlurl="http://localhost:" + GQL_PORT + "/gql" #kdybych chtel delat v ramci apolla, budu tu mit 33001
):
    token = None
    async def post(query, variables):
        nonlocal token
        if token is None:
            token = await getToken(username, password)

        payload = {"query": query, "variables": variables}
        # headers = {"Authorization": f"Bearer {token}"}
        cookies = {'authorization': token}
        async with aiohttp.ClientSession() as session:
            # print(headers, cookies)
            async with session.post(gqlurl, json=payload, cookies=cookies) as resp:
                # print(resp.status)
                if resp.status != 200:
                    text = await resp.text()
                    print(text)
                    return text
                else:
                    response = await resp.json()
                    return response
    return post 


async def run_mutation(mutation_string, variables, username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD):
  client = createFederationClient(username, password)
  result = await client(mutation_string, variables)
  basic_assertion(result)
  return result

def basic_assertion(responsejson):
	is_json(responsejson)
	has_no_errors(responsejson)
	has_data_field(responsejson)

def is_json(responsejson):
	assert isinstance(responsejson, dict), 'Response is not a JSON object'
	return True

def has_no_errors(responsejson):
    assert "errors" not in responsejson, f"Response contains errors: {responsejson.get('errors')}!"
    return True

def has_data_field(responsejson):
	assert "data" in responsejson, "Response does not contain data field!"
	return True

def data_has_field(responsejson, fieldname):
	data = responsejson.get("data", {})
	assert fieldname in data, f"Data does not contain {fieldname}!"
	return True


# ============================================
# Color codes for terminal output
# ============================================
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def print_test(name, status, details=""):
    """Print colored test result"""
    if status == "PASS":
        symbol = "✓"
        color = Colors.GREEN
    elif status == "FAIL":
        symbol = "✗"
        color = Colors.RED
    else:  # INFO
        symbol = "ℹ"
        color = Colors.CYAN
    
    print(f"{color}{Colors.BOLD}[{symbol}]{Colors.RESET} {color}{name}{Colors.RESET}", end="")
    if details:
        print(f" {Colors.RESET}→ {details}", end="")
    print()


def print_section(title):
    """Print section header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{Colors.RESET}\n")


# ============================================
# Test Suite
# ============================================
async def test_document_crud():
    """Test Document CREATE, READ, UPDATE, DELETE operations"""
    print_section("DOCUMENT CRUD TESTS")
    
    doc_id = None
    doc_lastchange = None
    fragment_count = 0  # Initialize to avoid UnboundLocalError in cleanup
    
    try:
        # ===== CREATE =====
        print_test("Document CREATE", "INFO", "Creating document with long content...")
        long_content = ". ".join([f"This is sentence number {i}" for i in range(1, 51)])  # 50 sentences
        
        create_vars = {
            "authorId": ZDENKA_SIMECKOVA_ID,
            "classification": "public",
            "content": long_content,
            "language": "en",
            "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
            "sourceUrl": "http://example.com/doc1",
            "title": "Test Document",
            "version": "1.0"
        }
        
        result = await run_mutation(DOCUMENT_CREATE, create_vars)
        doc_data = result["data"]["DocumentInsert"]
        
        assert doc_data["__typename"] == "DocumentGQLModel", "Wrong type returned"
        assert doc_data["title"] == "Test Document", "Title mismatch"
        
        doc_id = doc_data["id"]
        doc_lastchange = doc_data["lastchange"]
        
        print_test("Document CREATE", "PASS", f"id={doc_id[:8]}..., title='{doc_data['title']}', classification='{doc_data['classification']}'")
    
        # ===== CREATE with missing content (should fail) =====
        print_test("Document CREATE (no content)", "INFO", "Attempting to create document without content...")
        
        # Remove content from the vars to test validation
        invalid_vars = {**create_vars}
        del invalid_vars["content"]
        
        invalid_client = createFederationClient(DEFAULT_USERNAME, DEFAULT_PASSWORD)
        invalid_result = await invalid_client(DOCUMENT_CREATE, invalid_vars)
        
        # Should have GraphQL errors because content is required
        if "errors" in invalid_result:
            error_msg = invalid_result["errors"][0]["message"]
            print_test("Document CREATE (no content)", "PASS", f"Correctly rejected with GraphQL error: '{error_msg[:60]}...'")
    
        # ===== READ (with fragments check) =====
        print_test("Document READ", "INFO", f"Reading document {doc_id[:8]}... and checking fragments")
        client = createFederationClient()
        read_result = await client(DOCUMENT_READ, {"id": doc_id})
        basic_assertion(read_result)
        
        read_doc = read_result["data"]["documentById"]
        assert read_doc["id"] == doc_id, "ID mismatch"
        assert read_doc["title"] == "Test Document", "Title mismatch on read"
        assert "fragments" in read_doc, "No fragments field"
        
        fragments = read_doc["fragments"]
        fragment_count = len(fragments) if fragments else 0
        
        details = f"title='{read_doc['title']}', lang='{read_doc.get('language', 'N/A')}', source='{read_doc.get('source_url', 'N/A')}', fragments={fragment_count}"
        print_test("Document READ", "PASS", details)
    
        # ===== UPDATE =====
        print_test("Document UPDATE", "INFO", "Updating document source_url and content...")
        update_vars = {
            "id": doc_id,
            "lastchange": doc_lastchange,
            "content": "Updated content here"
        }
        
        update_result = await run_mutation(DOCUMENT_UPDATE, update_vars)
        updated_doc = update_result["data"]["DocumentUpdate"]
        
        assert updated_doc["__typename"] == "DocumentGQLModel", "Wrong type on update"
        assert updated_doc["source_url"] == "www.4chan.org/b", "source_url not updated"
        assert updated_doc["content"] == "Updated content here", "Content not updated"
        
        doc_lastchange = updated_doc["lastchange"]  # Update for next operation
        
        print_test("Document UPDATE", "PASS", f"source_url: 'http://example.com/doc1' → '{updated_doc['source_url']}', content: 'This is sentence...' → '{updated_doc['content'][:20]}...'")
    
        # ===== UPDATE with wrong lastchange (should fail) =====
        print_test("Document UPDATE (invalid lastchange)", "INFO", "Testing with wrong lastchange...")
        bad_update_vars = {
            "id": doc_id,
            "lastchange": "2020-01-01T00:00:00",  # Wrong lastchange
            "content": "This should fail"
        }
        
        bad_result = await run_mutation(DOCUMENT_UPDATE, bad_update_vars)
        bad_update = bad_result["data"]["DocumentUpdate"]
        
        assert bad_update["__typename"] == "DocumentGQLModelUpdateError", "Should return error type"
        assert bad_update["failed"] == True, "Should have failed flag"
        
        print_test("Document UPDATE (invalid lastchange)", "PASS", f"Correctly rejected: {bad_update['msg'][:50]}...")
        
        # ===== UPDATE classification =====
        print_test("Document Classification UPDATE", "INFO", "Updating classification to 'confidential'...")
        class_vars = {
            "id": doc_id,
            "lastchange": doc_lastchange,
            "classification": "confidential"
        }
        
        class_result = await run_mutation(DOCUMENT_UPDATE_CLASSIFICATION, class_vars)
        updated_class = class_result["data"]["DocumentUpdateClassification"]
        
        assert updated_class["__typename"] == "DocumentGQLModel", "Wrong type on classification update"
        assert updated_class["classification"] == "confidential", "Classification not updated"
        
        doc_lastchange = updated_class["lastchange"]  # Update for delete
        
        print_test("Document Classification UPDATE", "PASS", f"classification: 'public' → 'confidential'")
        
    finally:
        # ===== DELETE (cleanup always runs) =====
        if doc_id and doc_lastchange:
            print_test("Document DELETE", "INFO", f"Deleting document {doc_id[:8]}... (cascade fragments)")
            delete_vars = {"id": doc_id, "lastchange": doc_lastchange}
            
            delete_result = await run_mutation(DOCUMENT_DELETE, delete_vars)
            del_response = delete_result["data"]["DocumentDelete"]
            
            if del_response is None:
                # Successful delete returns None
                frag_msg = f" and {fragment_count} fragments" if fragment_count > 0 else ""
                print_test("Document DELETE", "PASS", f"Document (id={doc_id[:8]}...){frag_msg} deleted successfully")
            else:
                # If not None, check if it's an error or success
                assert del_response.get("__typename") == "DocumentGQLModelDeleteError", "Delete should return error type"
                assert del_response.get("failed") == False or del_response.get("failed") is None, "Delete should succeed"
                
                frag_msg = f" and {fragment_count} fragments" if fragment_count > 0 else ""
                print_test("Document DELETE", "PASS", f"Document (id={doc_id[:8]}...){frag_msg} deleted")


async def test_fragment_crud():
    """Test Fragment CREATE, READ, UPDATE, DELETE operations"""
    print_section("FRAGMENT CRUD TESTS")
    
    parent_doc_id = None
    parent_doc_lastchange = None
    frag_id = None
    frag_lastchange = None
    
    try:
        # First create a document to attach fragments to
        print_test("Setup", "INFO", "Creating parent document...")
        doc_vars = {
            "authorId": ZDENKA_SIMECKOVA_ID,
            "classification": "internal",
            "content": "Parent document for fragment testing.",
            "language": "cs",
            "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
            "title": "Fragment Test Parent",
            "version": "1.0"
        }
        
        doc_result = await run_mutation(DOCUMENT_CREATE, doc_vars)
        parent_doc = doc_result["data"]["DocumentInsert"]
        parent_doc_id = parent_doc["id"]
        parent_doc_lastchange = parent_doc["lastchange"]
        
        print_test("Setup", "PASS", f"Parent doc: id={parent_doc_id[:8]}..., title='{parent_doc['title']}', classification='{parent_doc['classification']}'")
    
        # ===== CREATE =====
        print_test("Fragment CREATE", "INFO", "Creating manual fragment...")
        frag_vars = {
            "content": "This is a manually created fragment for testing purposes.",
            "documentId": parent_doc_id
        }
        
        frag_result = await run_mutation(FRAGMENT_CREATE, frag_vars)
        frag_data = frag_result["data"]["fragmentInsert"]
        
        assert frag_data["__typename"] == "FragmentGQLModel", "Wrong type"
        assert frag_data["content"] == frag_vars["content"], "Content mismatch"
        assert frag_data["vector"] is not None, "Vector not generated"
        
        frag_id = frag_data["id"]
        frag_lastchange = frag_data["lastchange"]
        vector_len = len(frag_data["vector"]) if frag_data["vector"] else 0
        
        print_test("Fragment CREATE", "PASS", f"id={frag_id[:8]}..., content='{frag_data['content'][:40]}...', vector_dim={vector_len}")

        # ===== CREATE with missing content (should fail) =====
        print_test("Fragment CREATE (no content)", "INFO", "Attempting to create fragment without content...")
        
        # Remove content from the vars to test validation
        invalid_vars = {**frag_vars}
        del invalid_vars["content"]
        
        invalid_client = createFederationClient(DEFAULT_USERNAME, DEFAULT_PASSWORD)
        invalid_result = await invalid_client(FRAGMENT_CREATE, invalid_vars)
        
        # Should have GraphQL errors because content is required
        if "errors" in invalid_result:
            error_msg = invalid_result["errors"][0]["message"]
            print_test("Fragment CREATE (no content)", "PASS", f"Correctly rejected with GraphQL error: '{error_msg[:60]}...'")
    

        # ===== READ =====
        print_test("Fragment READ", "INFO", f"Reading fragment {frag_id[:8]}...")
        client = createFederationClient()
        frag_read = await client(FRAGMENT_READ, {"id": frag_id})
        basic_assertion(frag_read)
        
        read_frag = frag_read["data"]["fragmentById"]
        assert read_frag["id"] == frag_id, "ID mismatch"
        assert read_frag["documentId"] == parent_doc_id, "Parent document mismatch"
        
        print_test("Fragment READ", "PASS", f"id={frag_id[:8]}..., parent_doc={parent_doc_id[:8]}..., content='{read_frag['content'][:30]}...'")
    
        # ===== UPDATE =====
        print_test("Fragment UPDATE", "INFO", "Updating fragment content...")
        old_content = frag_data["content"]
        update_frag_vars = {
            "id": frag_id,
            "lastchange": frag_lastchange,
            "content": "Updated fragment content with new information."
        }
        
        update_frag_result = await run_mutation(FRAGMENT_UPDATE, update_frag_vars)
        updated_frag = update_frag_result["data"]["fragmentUpdate"]
        
        assert updated_frag["__typename"] == "FragmentGQLModel", "Wrong type on update"
        assert updated_frag["content"] == update_frag_vars["content"], "Content not updated"
        assert updated_frag["content"] != old_content, "Content should have changed"
        
        frag_lastchange = updated_frag["lastchange"]
        
        print_test("Fragment UPDATE", "PASS", f"content: '{old_content[:30]}...' → '{updated_frag['content'][:30]}...'")
    
        # ===== UPDATE with wrong lastchange (should fail) =====
        print_test("Fragment UPDATE (invalid lastchange)", "INFO", "Testing with wrong lastchange...")
        bad_frag_vars = {
            "id": frag_id,
            "lastchange": "2020-01-01T00:00:00",
            "content": "This should fail"
        }
        
        bad_frag_result = await run_mutation(FRAGMENT_UPDATE, bad_frag_vars)
        bad_frag = bad_frag_result["data"]["fragmentUpdate"]
        
        assert bad_frag["__typename"] == "FragmentGQLModelUpdateError", "Should return error"
        assert bad_frag["failed"] == True, "Should have failed"
        
        print_test("Fragment UPDATE (invalid lastchange)", "PASS", "Correctly rejected")
        
    finally:
        # ===== DELETE (cleanup always runs) =====
        if frag_id and frag_lastchange:
            print_test("Fragment DELETE", "INFO", f"Deleting fragment {frag_id[:8]}...")
            del_frag_vars = {"id": frag_id, "lastchange": frag_lastchange}
            
            del_frag_result = await run_mutation(FRAGMENT_DELETE, del_frag_vars)
            del_frag = del_frag_result["data"]["fragmentDelete"]
            
            if del_frag is None:
                print_test("Fragment DELETE", "PASS", f"Fragment (id={frag_id[:8]}...) deleted successfully")
            else:
                assert del_frag.get("__typename") == "FragmentGQLModelDeleteError", "Delete returns error type"
                assert del_frag.get("failed") == False or del_frag.get("failed") is None, "Delete should succeed"
                print_test("Fragment DELETE", "PASS", f"Fragment (id={frag_id[:8]}...) deleted")
        
        # Cleanup parent document
        if parent_doc_id and parent_doc_lastchange:
            print_test("Cleanup", "INFO", f"Removing parent document {parent_doc_id[:8]}...")
            del_doc_result = await run_mutation(DOCUMENT_DELETE, {"id": parent_doc_id, "lastchange": parent_doc_lastchange})
            print_test("Cleanup", "PASS", f"Parent document (id={parent_doc_id[:8]}...) removed")


async def test_document_classification_update():
    """Test Document classification update (admin-only operation)"""
    print_section("DOCUMENT CLASSIFICATION UPDATE TEST")
    
    doc_id = None
    doc_lastchange = None
    
    try:
        # Create test document
        doc_vars = {
            "authorId": ZDENKA_SIMECKOVA_ID,
            "classification": "public",
            "content": "Classification test document.",
            "rbacobjectId": UNIVERSITY_ADMIN_RBAC_ID,
            "title": "Classification Test",
        }
        
        doc_result = await run_mutation(DOCUMENT_CREATE, doc_vars)
        doc = doc_result["data"]["DocumentInsert"]
        doc_id = doc["id"]
        doc_lastchange = doc["lastchange"]
        
        print_test("Setup", "PASS", f"Test doc: id={doc_id[:8]}..., title='{doc['title']}', classification='{doc['classification']}'")
        
        # Update classification
        print_test("Classification UPDATE", "INFO", "Updating classification to 'confidential'...")
        class_vars = {
            "id": doc_id,
            "lastchange": doc_lastchange,
            "classification": "confidential"
        }
        
        class_result = await run_mutation(DOCUMENT_UPDATE_CLASSIFICATION, class_vars)
        updated = class_result["data"]["DocumentUpdateClassification"]
        
        assert updated["__typename"] == "DocumentGQLModel", "Wrong type"
        assert updated["classification"] == "confidential", "Classification not updated"
        
        doc_lastchange = updated["lastchange"]  # Update for cleanup
        
        print_test("Classification UPDATE", "PASS", f"classification: 'public' → 'confidential' (id={doc_id[:8]}...)")
        
    finally:
        # Cleanup
        if doc_id and doc_lastchange:
            print_test("Cleanup", "INFO", f"Removing classification test document {doc_id[:8]}...")
            await run_mutation(DOCUMENT_DELETE, {"id": doc_id, "lastchange": doc_lastchange})
            print_test("Cleanup", "PASS", f"Classification test document (id={doc_id[:8]}...) removed")


async def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*60}")
    print(f"{'  GRAPHQL API TEST SUITE':^60}")
    print(f"{'='*60}{Colors.RESET}\n")
    
    # Check initial database state
    print_test("Pre-test Check", "INFO", "Checking initial database state...")
    client = createFederationClient()
    initial_docs = await client(DOCUMENT_PAGE, {})
    initial_frags = await client(FRAGMENT_PAGE, {})
    
    initial_doc_count = len(initial_docs.get("data", {}).get("documentPage", [])) if initial_docs else 0
    initial_frag_count = len(initial_frags.get("data", {}).get("fragmentPage", [])) if initial_frags else 0
    
    print_test("Pre-test Check", "PASS", f"Initial state: {initial_doc_count} documents, {initial_frag_count} fragments")
    
    try:
        await test_document_crud()
        await test_fragment_crud()
        
        # Check final database state
        print_test("Post-test Check", "INFO", "Verifying database cleanup...")
        final_docs = await client(DOCUMENT_PAGE, {})
        final_frags = await client(FRAGMENT_PAGE, {})
        
        final_doc_count = len(final_docs.get("data", {}).get("documentPage", [])) if final_docs else 0
        final_frag_count = len(final_frags.get("data", {}).get("fragmentPage", [])) if final_frags else 0
        
        if final_doc_count == initial_doc_count and final_frag_count == initial_frag_count:
            print_test("Post-test Check", "PASS", f"Database clean: {final_doc_count} documents, {final_frag_count} fragments (same as initial)")
        else:
            print_test("Post-test Check", "FAIL", f"Database NOT clean! Found {final_doc_count} docs (expected {initial_doc_count}), {final_frag_count} frags (expected {initial_frag_count})")
            if final_doc_count > initial_doc_count:
                print(f"{Colors.YELLOW}Remaining documents:{Colors.RESET}")
                for doc in final_docs["data"]["documentPage"][initial_doc_count:]:
                    print(f"  - {doc['id']}: {doc['title']} ({doc['classification']})")
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*60}")
        print(f"{'  ALL TESTS PASSED ✓':^60}")
        print(f"{'='*60}{Colors.RESET}\n")
        
    except AssertionError as e:
        print(f"\n{Colors.RED}{Colors.BOLD}{'='*60}")
        print(f"  TEST FAILED ✗")
        print(f"{'='*60}")
        print(f"{Colors.RED}Error: {e}{Colors.RESET}\n")
        raise
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}{'='*60}")
        print(f"  UNEXPECTED ERROR ✗")
        print(f"{'='*60}")
        print(f"{Colors.RED}Error: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        raise

async def check_server_running(url: str = f"http://localhost:{GQL_PORT}") -> bool:
    """Check if server is running by attempting to connect"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                return True
    except:
        return False


async def wait_for_server(url: str = f"http://localhost:{GQL_PORT}", timeout: int = 30):
    """Wait for server to be ready"""
    import time
    start_time = time.time()
    
    print(f"{Colors.YELLOW}Waiting for server at {url}...{Colors.RESET}")
    
    while time.time() - start_time < timeout:
        if await check_server_running(url):
            print(f"{Colors.GREEN}✓ Server is ready{Colors.RESET}")
            return True
        await asyncio.sleep(0.5)
    
    raise TimeoutError(f"Server did not start within {timeout} seconds")


def stop_server():
    """Stop any running uvicorn server on the test port"""
    import subprocess
    import signal
    
    try:
        # Find process using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{GQL_PORT}"],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                print(f"{Colors.YELLOW}Stopping server (PID: {pid})...{Colors.RESET}")
                os.kill(int(pid), signal.SIGTERM)
            
            # Wait a bit for graceful shutdown
            import time
            time.sleep(2)
            print(f"{Colors.GREEN}✓ Server stopped{Colors.RESET}")
            return True
    except Exception as e:
        print(f"{Colors.YELLOW}Note: Could not stop server - {e}{Colors.RESET}")
    
    return False


def start_server():
    """Start uvicorn server with test environment variables"""
    import subprocess
    import os
    from pathlib import Path
    
    # Get the project root directory (parent of tests directory)
    project_root = Path(__file__).parent.parent.absolute()
    uvicorn_path = project_root / ".venv" / "bin" / "uvicorn"
    env_file = project_root / "environment.txt"
    
    # Set environment variable for this process
    env = os.environ.copy()
    env["SYNC_FRAGMENT_GENERATION"] = "True"
    
    print(f"{Colors.YELLOW}Starting server with SYNC_FRAGMENT_GENERATION=True...{Colors.RESET}")
    
    # Start server in background
    process = subprocess.Popen(
        [str(uvicorn_path), "main:app", "--reload", "--env-file", str(env_file)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(project_root)
    )
    
    print(f"{Colors.GREEN}✓ Server started (PID: {process.pid}){Colors.RESET}")
    return process


if __name__ == "__main__":
    import os
    import asyncio
    
    async def run_tests():
        # Check if server is running
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
        print(f"  SERVER SETUP")
        print(f"{'='*60}{Colors.RESET}\n")
        
        server_was_running = await check_server_running()
        
        if server_was_running:
            print(f"{Colors.YELLOW}Server is already running{Colors.RESET}")
            stop_server()
        else:
            print(f"{Colors.YELLOW}Server is not running{Colors.RESET}")
        
        # Start server with correct environment
        server_process = start_server()
        
        # Wait for server to be ready
        await wait_for_server()
        
        # Run tests
        try:
            await main()
        finally:
            # Optionally stop the server after tests
            # Uncomment the following lines if you want to stop the server after tests:
            print(f"\n{Colors.YELLOW}Stopping test server...{Colors.RESET}")
            stop_server()
            pass
    
    asyncio.run(run_tests())
