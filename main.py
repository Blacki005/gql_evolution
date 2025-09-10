import os
import socket
import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, FileResponse
from strawberry.fastapi import GraphQLRouter

import logging
import logging.handlers

from src.GraphTypeDefinitions import schema
from src.DBDefinitions import startEngine, ComposeConnectionString
from src.DBFeeder import initDB

# region logging setup

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s.%(msecs)03d\t%(levelname)s:\t%(message)s', 
    datefmt='%Y-%m-%dT%I:%M:%S')
SYSLOGHOST = os.getenv("SYSLOGHOST", None)
if SYSLOGHOST is not None:
    [address, strport, *_] = SYSLOGHOST.split(':')
    assert len(_) == 0, f"SYSLOGHOST {SYSLOGHOST} has unexpected structure, try `localhost:514` or similar (514 is UDP port)"
    port = int(strport)
    my_logger = logging.getLogger()
    my_logger.setLevel(logging.INFO)
    handler = logging.handlers.SysLogHandler(address=(address, port), socktype=socket.SOCK_DGRAM)
    #handler = logging.handlers.SocketHandler('10.10.11.11', 611)
    my_logger.addHandler(handler)

# endregion

# region DB setup

## Definice GraphQL typu (pomoci strawberry https://strawberry.rocks/)
## Strawberry zvoleno kvuli moznosti mit federovane GraphQL API (https://strawberry.rocks/docs/guides/federation, https://www.apollographql.com/docs/federation/)
## Definice DB typu (pomoci SQLAlchemy https://www.sqlalchemy.org/)
## SQLAlchemy zvoleno kvuli moznost komunikovat s DB asynchronne
## https://docs.sqlalchemy.org/en/14/core/future.html?highlight=select#sqlalchemy.future.select


## Zabezpecuje prvotni inicializaci DB a definovani Nahodne struktury pro "Univerzity"
# from gql_workflow.DBFeeder import createSystemDataStructureRoleTypes, createSystemDataStructureGroupTypes

connectionString = ComposeConnectionString()

def singleCall(asyncFunc):
    """Dekorator, ktery dovoli, aby dekorovana funkce byla volana (vycislena) jen jednou. Navratova hodnota je zapamatovana a pri dalsich volanich vracena.
    Dekorovana funkce je asynchronni.
    """
    resultCache = {}

    async def result():
        if resultCache.get("result", None) is None:
            resultCache["result"] = await asyncFunc()
        return resultCache["result"]

    return result

@singleCall
async def RunOnceAndReturnSessionMaker():
    """Provadi inicializaci asynchronniho db engine, inicializaci databaze a vraci asynchronni SessionMaker.
    Protoze je dekorovana, volani teto funkce se provede jen jednou a vystup se zapamatuje a vraci se pri dalsich volanich.
    """

    makeDrop = os.getenv("DEMO", None) == "True"
    logging.info(f'starting engine for "{connectionString} makeDrop={makeDrop}"')

    result = await startEngine(
        connectionstring=connectionString, makeDrop=makeDrop, makeUp=True
    )   
    assert result is not None, "Unable to start engine"
    ###########################################################################################################################
    #
    # zde definujte do funkce asyncio.gather
    # vlozte asynchronni funkce, ktere maji data uvest do prvotniho konzistentniho stavu
    async def initDBAndReport():
        logging.info(f"initializing system structures")
        await initDB(result)
        logging.info(f"all done")
        print(f"all done")

    # asyncio.create_task(coro=initDBAndReport())
    await initDBAndReport()

    #
    #
    ###########################################################################################################################
    
    return result

# endregion

# region FastAPI setup
async def get_context(request: Request):
    asyncSessionMaker = await RunOnceAndReturnSessionMaker()
        
    from src.Dataloaders import createLoadersContext
    context = createLoadersContext(asyncSessionMaker)

    result = {**context}
    result["request"] = request
    return result

innerlifespan = None
@asynccontextmanager
async def dummy(app: FastAPI):
    yield 

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.DBFeeder import backupDB
    icm = dummy if innerlifespan is None else innerlifespan
    async with icm(app):
        print(f"FastAPI.lifespan {innerlifespan is None}")
        initizalizedEngine = await RunOnceAndReturnSessionMaker()
        try:
            yield
        finally:
            pass
        await backupDB(initizalizedEngine)
    
    # print("App shutdown, nothing to do")

app = FastAPI(lifespan=lifespan)

graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context
)

from uoishelpers.schema import SessionCommitExtensionFactory
from src.Dataloaders import createLoadersContext
schema.extensions.append(
    SessionCommitExtensionFactory(session_maker_factory=RunOnceAndReturnSessionMaker, loaders_factory=createLoadersContext)
)


app.include_router(graphql_app, prefix="/gql")

@app.get("/voyager", response_class=FileResponse)
async def graphiql():
    realpath = os.path.realpath("./src/Htmls/voyager.html")
    return realpath

@app.get("/doc", response_class=FileResponse)
async def graphiql():
    realpath = os.path.realpath("./src/Htmls/liveschema.html")
    return realpath

@app.get("/ui", response_class=FileResponse)
async def graphiql():
    realpath = os.path.realpath("./src/Htmls/livedata.html")
    return realpath

@app.get("/test", response_class=FileResponse)
async def graphiql():
    realpath = os.path.realpath("./src/Htmls/tests.html")
    return realpath

import prometheus_client
@app.get("/metrics")
async def metrics():
    return Response(
        content=prometheus_client.generate_latest(), 
        media_type=prometheus_client.CONTENT_TYPE_LATEST
        )


logging.info("All initialization is done")

# @app.get('/hello')
# def hello():
#    return {'hello': 'world'}

###########################################################################################################################
#
# pokud jste pripraveni testovat GQL funkcionalitu, rozsirte apollo/server.js
#
###########################################################################################################################
# endregion

# region ENV setup tests
def envAssertDefined(name, default=None):
    result = os.getenv(name, None)
    assert result is not None, f"{name} environment variable must be explicitly defined"
    return result

DEMO = envAssertDefined("DEMO", None)
GQLUG_ENDPOINT_URL = envAssertDefined("GQLUG_ENDPOINT_URL", None)

assert (DEMO in ["True", "true", "False", "false"]), "DEMO environment variable can have only `True` or `False` values"
DEMO = DEMO in ["True", "true"]

if DEMO:
    print("####################################################")
    print("#                                                  #")
    print("# RUNNING IN DEMO                                  #")
    print("#                                                  #")
    print("####################################################")

    logging.info("####################################################")
    logging.info("#                                                  #")
    logging.info("# RUNNING IN DEMO                                  #")
    logging.info("#                                                  #")
    logging.info("####################################################")
else:
    print("####################################################")
    print("#                                                  #")
    print("# RUNNING DEPLOYMENT                               #")
    print("#                                                  #")
    print("####################################################")

    logging.info("####################################################")
    logging.info("#                                                  #")
    logging.info("# RUNNING DEPLOYMENT                               #")
    logging.info("#                                                  #")
    logging.info("####################################################")    

logging.info(f"DEMO = {DEMO}")
logging.info(f"SYSLOGHOST = {SYSLOGHOST}")
logging.info(f"GQLUG_ENDPOINT_URL = {GQLUG_ENDPOINT_URL}")

# endregion

# region nicegui
from main_nicegui import nicegui, nicegui_app
nicegui.ui.run_with(
    app,
    title="GQL Evolution",
    mount_path="/nicegui",
    favicon="🚀",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET")
# endregion

# region mcp
from main_mcp import mcp_app, mcp_app_sse, Client
innerlifespan = mcp_app.lifespan

app.mount(path="/mcp", app=mcp_app_sse)
app.mount(path="/mcp_no_sse", app=mcp_app)


@app.get("/testmcp")
async def test_mcp() -> dict:
    # client = Client(mcp_app)
    client = Client("http://localhost:8002/mcp_no_sse")
    result = {}
    async with client:
        result["tool.response"] = await client.call_tool("echo", {"text": "hello"})

        resources = await client.list_resource_templates()
        tools = await client.list_tools()
        print(f"tools: {tools}")
        # Filter resources by tag
        result["config_resources"] = [
            resource for resource in resources 
            # if hasattr(resource, '_meta') and resource._meta and
            #     resource._meta.get('_fastmcp', {}) and
            #     'config' in resource._meta.get('_fastmcp', {}).get('tags', [])
        ]        
    return result
# endregion


@app.middleware("http")
async def add_process_log(request: Request, call_next):
    print(f"http.middleware base_url={request.base_url}")
    response = await call_next(request)
    return response

@mcp_app.middleware("http")
async def add_process_log(request: Request, call_next):
    print(f"mcp.http.middleware base_url={request.base_url}")
    try:
        response = await call_next(request)
    except Exception as e:
        print("chyba {e}")
        raise e
    return response
# v následujícím dotazu identifikuj datové entity, a podmínky, které mají splňovat. seznam datových entit (jejich odhadnuté názvy) uveď jako json list obsahující stringy - názvy seznam podmínek uveď jako json list obsahující dict např. {"name": {"_eq": "Pavel"}} pokud se jedná o podmínku v relaci, odpovídající dict je tento {"related_entity": {"attribute_name": {"_eq": "value"}}} v dict nikdy není použit klíč, který by sdružoval více názvů atributů dotaz: najdi mi všechny uživatele, kteří jsou členy katedry K209