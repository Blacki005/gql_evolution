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

from nicegui import core
import nicegui
@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.DBFeeder import backupDB
    initizalizedEngine = await RunOnceAndReturnSessionMaker()
    # core.loop = asyncio.get_event_loop()
    # core.app.config = nicegui.app.AppConfig()
    # await core.startup()
    try:
        yield
    finally:
        # await core.shutdown()
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
from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware
nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key='SUPER-SECRET')
from graphql import parse

@ui.page("/")
async def index_page():
    # https://github.com/zauberzeug/nicegui/blob/main/examples/chat_with_ai/main.py

    # print("Index page", type(request), type(response), type(unknown))
    # ui.label("Hello, World!")
    # ui.button("Click me", on_click=lambda: ui.notify("Clicked!"))
    async def send() -> None:
        question = text.value
        text.value = ''
        with message_container:
            ui.chat_message(text=question, name='You', sent=True).classes("no-tail")
            response_message = ui.chat_message(name='Bot', sent=False).classes("no-tail")
        
        if question.strip() == "sdl":
            response = [
                {"type": "text", "content": f"I have responded to {question}"},
                {"type": "md", "content": schema.as_str().replace("\\n", "\n").replace('\\"', '"') }
            ]
        elif question.strip() == "explain":
            from src.Utils.explain_query import explain_graphql_query
            from src.Utils.gql_client import createGQLClient
            client = await createGQLClient(username="john.newbie@world.com", password="john.newbie@world.com")
            sdl_query = """query __ApolloGetServiceDefinition__ { _service { sdl } }"""
            result = await client(sdl_query, variables={})
            print(result)
            sdl = result["data"]["_service"]["sdl"]
            schema_ast = parse(sdl)
            # sdl = schema.as_str()
            query = """
query userPage($skip: Int, $limit: Int, $orderby: String, $where: UserInputWhereFilter) {
  userPage(skip: $skip, limit: $limit, orderby: $orderby, where: $where) {
  __typename
id
lastchange
created

name
givenname
middlename
email
firstname
surname
valid
startdate
enddate
}
}
"""
            result = explain_graphql_query(schema_ast, query)
            response = [
                {"type": "text", "content": f"I have responded to {question}"},
                {"type": "md", "content": f"```gql\n{result}\n```"} 
            ]
        else:
            response = [
                {"type": "text", "content": f"I have responded to {question}"},
                {"type": "md", "content": """
                            # My response
                            ```json
                            {
                                "question": "{question}"
                            }
                            ```
                            """
                            }
            ]
        for part in response:
            # await asyncio.sleep(1)
            if part["type"] == "text":
                with response_message:
                    ui.html(part["content"])
            elif part["type"] == "md":
                with message_container:
                    ui.markdown(part["content"])
        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

        # text.value = ''

    ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
    # ui.add_css("""
    # .q-chat-message--sent .q-message-container:before,
    # .q-chat-message--received .q-message-container:before {
    #     display: none !important;
    # }
    # """)
    ui.add_css("""
    .hide-zobacek:before {
        display: none !important;
    }
    """)
    ui.add_css("""
.no-tail .q-message-text--sent:before,
.no-tail .q-message-text--sent:after,
.no-tail .q-message-text--received:before,
.no-tail .q-message-text--received:after {
    display: none !important;
    content: none !important;
}
""")
    # the queries below are used to expand the contend down to the footer (content can then use flex-grow to expand)
    ui.query('.q-page').classes('flex')
    ui.query('.nicegui-content').classes('w-full')

    with ui.tabs().classes('w-full') as tabs:
        chat_tab = ui.tab('Chat')
        logs_tab = ui.tab('Logs')
    with ui.tab_panels(tabs, value=chat_tab).classes('w-full max-w-5xl mx-auto flex-grow items-stretch'): #.classes('w-full max-w-2xl mx-auto flex-grow items-stretch'):
        message_container = ui.tab_panel(chat_tab).classes('items-stretch')
        with message_container:
            ui.chat_message(text="I have arrived", name='You', sent=True).classes("no-tail")
            ui.chat_message(text="Hello! I'm your friendly bot. How can I assist you today?", name='Bot', sent=False).classes("no-tail")
            ui.markdown("""
                        # My response
                        ```json
                        {
                            "question": "{question}"
                        }
                        ```
                        """
                        """I have responded to {question}""")
            
            # ui.chat_message(text="Hi! How can I help you?", name='Bot', sent=False)
        with ui.tab_panel(logs_tab):
            log = ui.log().classes('w-full h-full') 

    with ui.footer().classes("bg-gray-600"), ui.column().classes('w-full max-w-3xl mx-auto my-6'):
        with ui.row().classes('w-full no-wrap items-center'):
            placeholder = ("message" 
                # if "OPENAI_API_KEY" != 'not-set' else \
                # 'Please provide your OPENAI key in the Python script first!'
            )
            text = ui.input(label="User query", placeholder=placeholder).props('rounded outlined input-class mx-3') \
                .classes('w-full self-center').on('keydown.enter', send)


# app.mount("/nicegui", nicegui_app)
nicegui.ui.run_with(
    app,
    title="GQL Evolution",
    favicon="🚀",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET")
# endregion


# v následujícím dotazu identifikuj datové entity, a podmínky, které mají splňovat. seznam datových entit (jejich odhadnuté názvy) uveď jako json list obsahující stringy - názvy seznam podmínek uveď jako json list obsahující dict např. {"name": {"_eq": "Pavel"}} pokud se jedná o podmínku v relaci, odpovídající dict je tento {"related_entity": {"attribute_name": {"_eq": "value"}}} v dict nikdy není použit klíč, který by sdružoval více názvů atributů dotaz: najdi mi všechny uživatele, kteří jsou členy katedry K209