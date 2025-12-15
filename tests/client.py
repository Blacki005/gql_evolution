import aiohttp
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
            print(resp.status)
            keyJson = await resp.json()
            print(keyJson)

        payload = {"key": keyJson["key"], "username": username, "password": password}
        async with session.post(keyurl, json=payload) as resp:
            print(resp.status)
            tokenJson = await resp.json()
            print(tokenJson)
    return tokenJson.get("token", None)
            

def createFederationClient(
    username="john.newbie@world.com", 
    password="john.newbie@world.com",
    gqlurl="http://localhost:8000/gql" #kdybych chtel delat v ramci apolla, budu tu mit 33001
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

def is_json(responsejson):
	assert isinstance(responsejson, dict), 'Response is not a JSON object'
	return True

def has_no_errors(responsejson):
    assert "errors" not in responsejson, f"response contains errors: {responsejson.get('errors')}"
    return True

def has_data_field(responsejson):
	assert "data" in responsejson, "response does not contain data field"
	return True

def data_has_field(responsejson, fieldname):
	data = responsejson.get("data", {})
	assert fieldname in data, f"data does not contain {fieldname}"
	return True

def basic_assertion(responsejson):
	is_json(responsejson)
	has_no_errors(responsejson)
	has_data_field(responsejson)

async def document_insert_test():
    variables = {
        "classification": "Tajné",
        "content": "Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Sed convallis magna eu sem. Fusce dui leo, imperdiet in, aliquam sit amet, feugiat eu, orci. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Cras pede libero, dapibus nec, pretium sit amet, tempor quis. Pellentesque ipsum. Duis risus. Mauris tincidunt sem sed arcu. In laoreet, magna id viverra tincidunt, sem odio bibendum justo, vel imperdiet sapien wisi sed libero. Morbi scelerisque luctus velit.Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Maecenas ipsum velit, consectetuer eu lobortis ut, dictum at dui. Maecenas fermentum, sem in pharetra pellentesque, velit turpis volutpat ante, in pharetra metus odio a lectus. Morbi imperdiet, mauris ac auctor dictum, nisl ligula egestas nulla, et sollicitudin sem purus in lacus. Integer imperdiet lectus quis justo. Class aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos hymenaeos. Nunc dapibus tortor vel mi dapibus sollicitudin. Etiam neque. Etiam commodo dui eget wisi. Suspendisse sagittis ultrices augue. Mauris dolor felis, sagittis at, luctus sed, aliquam non, tellus. Nullam sapien sem, ornare ac, nonummy non, lobortis a enim. Nulla accumsan, elit sit amet varius semper, nulla mauris mollis quam, tempor suscipit diam nulla vel leo. Nullam eget nisl. Vivamus porttitor turpis ac leo. Sed ac dolor sit amet purus malesuada congue. Nulla accumsan, elit sit amet varius semper, nulla mauris mollis quam, tempor suscipit diam nulla vel leo. Duis sapien nunc, commodo et, interdum suscipit, sollicitudin et, dolor.",
        "language": "cs",
        "rbacobjectId": "d75d64a4-bf5f-43c5-9c14-8fda7aff6c09",
        "sourceUrl": "www.acrmemes.cz",
        "title": "Lorem Ipsum",
        "version": "42.0"
    }
    client = createFederationClient()
    result = await client("""
        mutation documentInsert($authorId: UUID, $classification: String, $content: String!, $language: String, $rbacobjectId: UUID!, $sourceUrl: String, $title: String, $version: String) {
        DocumentInsert(
            Document: {authorId: $authorId, classification: $classification, content: $content, language: $language, rbacobjectId: $rbacobjectId, sourceUrl: $sourceUrl, title: $title, version: $version}
        ) {
            ... on DocumentGQLModel {
            id
            lastchange
            title
            content
            classification
            source_url
            fragments {
                id
                lastchange
                content
                }
            }
            ... on InsertError {
            code
            location
            failed
            input
            msg
            }
        }
        }
    """,
    variables
    )
    return result
     

async def main():
    client = createFederationClient()
    result = await client("""
query {
  documentPage {
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
}""", {})
    basic_assertion(result)
    
    print("\033[92mOK\033[0m")

    print ("Running document insert test...")
    result = await document_insert_test()
    print(result)

if __name__ == "__main__":
    
    import asyncio
    asyncio.run(main())
