import json
import typing

# region nicegui
import nicegui
from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware
nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key='SUPER-SECRET')
from graphql import parse

from src.GraphTypeDefinitions import schema
from main_ai import ChatSession, MCPRouter, RouterContext, FilterType
import fastmcp

MCPURL = "http://localhost:8002/mcp_no_sse"

import traceback

def exception_to_markdown(exc: Exception) -> str:
    """Return a Markdown-formatted report for the given exception."""
    # Získáme traceback jako list FrameSummary

    # Hlavní hláška
    md = ["## ⚠️ Exception Report", ""]
    md.append(f"**Type:** `{type(exc).__name__}`  ")
    md.append(f"**Message:** `{exc}`  ")

    # Tabulka s trasou
    md.append("\n### Traceback\n")
    md.append("| File | Line | Function | Code |")
    md.append("|------|------|----------|------|")

    tb_list = traceback.extract_tb(exc.__traceback__)
    for frame in tb_list:
        md.append(
            f"| `{frame.filename}` | {frame.lineno} | `{frame.name}` | `{frame.line or ''}` |"
        )

    return "\n".join(md)



def GraphQLData(
    *,
    gqlclient: typing.Callable[[str, typing.Dict[str, typing.Any]], typing.Awaitable[dict]],
    query: str,
    variables: typing.Optional[typing.Dict[str, typing.Any]] = None,
    result: typing.Optional[typing.List[typing.Dict[str, typing.Any]]] = None,
    metadata: typing.Optional[typing.List[typing.Dict[str, typing.Any]]] = None,
    # extract_rows: typing.Optional[typing.Callable[[typing.Dict[str, typing.Any]], typing.List[typing.Dict[str, typing.Any]]]] = None,
    autoload: bool = True,
):
    """Composite NiceGUI widget to page GraphQL list results and show them in a table.

    Args:
        gqlclient: async function (query, variables) -> {"data": {...}, "errors": ...}
        query: GraphQL query string
        variables: initial variables; uses 'skip' and 'limit' for paging
        result: initial rows (optional)
        autoload: if True and no initial result, automatically loads first page
    """
    if variables is None:
        variables = {}
    if result is None:
        result = []
    if isinstance(result, dict):
        result = next(iter(result.values()), None)
    if metadata is None:
        metadata = {}

    state = {
        "variables": {
            **variables,
            "skip": variables.get("skip", 0),
            "limit": variables.get("limit", 10)
        },
        "errors": [],
        "result": list(result),
        "ids": {r.get("id") for r in result if isinstance(r, dict) and "id" in r and r["id"] is not None},
        "loading": False,
        "done": False
    }

    # def default_extract_rows(data: typing.Dict[str, typing.Any]) -> typing.List[typing.Dict[str, typing.Any]]:
    #     if not data:
    #         return []

    #     for v in data.values():
    #         if isinstance(v, list):
    #             return [x for x in v if isinstance(x, dict)]
    #     return []

    # extractor = extract_rows or default_extract_rows

    def compute_done(new_count: int) -> None:
        # If server returned fewer rows than limit → jsme na konci.
        limit = state["variables"].get("limit", 10)
        state["done"] = (limit == 0) or (new_count < limit)

    compute_done(new_count=len(result))
    async def reload_all():
        state["result"].clear()
        state["ids"].clear()
        state["variables"]["skip"] = 0
        state["done"] = False
        await load_page(skip=0)
    

    async def load_page(skip: typing.Optional[int] = None):
        if state["loading"]:
            return
        state["loading"] = True
        view.refresh()
        try:
            vars_now = dict(state["variables"])
            if skip is not None:
                vars_now["skip"] = skip
            else:
                vars_now["skip"] = vars_now.get("skip", 0) + vars_now.get("limit", 10)
            print(f"load_page.variables={vars_now}")
            response = await gqlclient(query, vars_now)
            errors = response.get("errors")
            if errors:
                state["errors"] = errors if isinstance(errors, list) else [errors]
                return
            data = response.get("data") or {}
            # rows = extractor(data)
            rows = next((value for value in data.values()), [])
            if not isinstance(rows, list):
                state["errors"] = ["response has nonlist key, this is not expected"]
                rows = []
            # append unique
            # new_added = 0
            for row in rows:
                rid = row.get("id")
                if rid is not None and rid not in state["ids"]:
                    state["result"].append(row)
                    if rid is not None:
                        state["ids"].add(rid)
                    # new_added += 1

            state["variables"] = {
                **vars_now
            }
            compute_done(len(rows))
        except Exception as e:
            state["errors"] = [f"{type(e).__name__}: {e}"]
        finally:
            state["loading"] = False
            view.refresh()

    async def load_more():
        print(f"load_more")
        await load_page()

    def getcolumns():
        rows = state["result"]
        if len(rows) == 0:
            return []
        return [
            { "name": key, "label": key, "field": key, "sortable": True }
            for key, value in rows[0].items()
            if not isinstance(value, (dict, list))
        ]
    
    @ui.refreshable
    def view():
        # fullscreen = ui.fullscreen()    
        # ui.button('Toggle Fullscreen', on_click=fullscreen.toggle)
        with ui.tabs() as tabs:
            queryTab = ui.tab('query')
            varTab = ui.tab('variables')
            rawresultTab = ui.tab('rawresult')
            resultTab = ui.tab('result')
        with ui.tab_panels(tabs, value=resultTab).classes('w-full'):
            with ui.tab_panel(queryTab):
                # ui.label('queryTab tab')
                ui.markdown((
                    "```graphql\n"
                    f"{query}"
                    "\n```"
                ))
            with ui.tab_panel(varTab):
                # ui.label('varTab tab')
                ui.markdown((
                    "```json\n"
                    f'{json.dumps(state["variables"], indent=2)}'
                    "\n```"
                ))
            with ui.tab_panel(rawresultTab):
                ui.markdown((
                    "## Raw Result\n\n"
                    "```json\n"
                    f"{json.dumps(state['result'], indent=2)}"
                    "\n```\n"
                    "## Metadata\n\n"
                    "```json\n"
                    f"{json.dumps(metadata, indent=2)}"
                    "\n```"
                    
                ))
            with ui.tab_panel(resultTab):
                # ui.markdown((
                #     "```json\n"
                #     f"{json.dumps(state['result'], indent=2)}"
                #     "\n```"
                # ))
                ui.table(
                    columns=getcolumns(),
                    rows=state["result"],
                    row_key="id"
                )
        if state["errors"]:
            ui.markdown("```text\n" + "\n".join(map(str, state["errors"])) + "\n```")

        with ui.row().classes('gap-2 mt-2'):
            
            ui.button(
                "Reload",
                on_click=reload_all,
                # ena=state["loading"],
            )
            ui.button(
                "Load more",
                on_click=load_more,
                # disable=state["loading"] or state["done"],
            )
            if state["loading"]:
                ui.spinner(size="md")

            if state["done"]:
                ui.label("No more data").classes('text-xs text-gray-500')

        pass

    view()
    # optional first fetch
    if autoload and not state["result"]:
        ui.timer(0, load_more, once=True)

    return view


from mcp.types import SamplingMessage, CreateMessageRequestParams, TextContent

def createOnSample(
    chatSession: ChatSession,
    onLog: typing.Callable[[str], None],
    onMessage: typing.Callable[[str], typing.Awaitable[None]],
    defaultParams: CreateMessageRequestParams = CreateMessageRequestParams(
        messages=[],
        maxTokens=1000
    )
):
    """
    Vytvoří callback onSampling(messages, params, context) pro sampling nad LLM.
    - messages: List[SamplingMessage] (každý má content nebo content.text)
    - params: CreateMessageRequestParams (očekává systemPrompt, temperature, max_tokens)
    - onLog: sync logger (str) -> None
    - onMessage: async notifier (str) -> Awaitable[None]
    """
    def _coalesce(*vals):
        for v in vals:
            if v is not None:
                return v
        return None

    def _clamp(x, lo, hi):
        return max(lo, min(hi, x))

    async def onSampling(
        messages: typing.List[SamplingMessage],
        params: CreateMessageRequestParams,
        context
    ):
        # 1) Merge parametrů s defaulty
        system_prompt = getattr(params, "systemPrompt", None)
        temperature = _coalesce(
            getattr(params, "temperature", None),
            getattr(defaultParams, "temperature", None),
            0.8
        )
        try:
            temperature = float(temperature)
        except Exception:
            temperature = 0.8
        temperature = _clamp(temperature, 0.0, 2.0)

        max_tokens = _coalesce(
            getattr(params, "max_tokens", None),
            getattr(defaultParams, "max_tokens", None),
            1000
        )
        try:
            max_tokens = int(max_tokens)
        except Exception:
            max_tokens = 1000
        if max_tokens <= 0:
            max_tokens = 1000

        # 2) Vyber aktuální chat session (nové se systémovým promptem, nebo reuse)
        currentChatSession = (
            ChatSession(system_prompt)
            if system_prompt
            else chatSession
        )

        # 3) Sestav dotaz z messages
        parts: typing.List[str] = []
        for message in messages:
            text = None
            try:
                content = getattr(message, "content", message)
                if isinstance(content, str):
                    text = content
                else:
                    # podpora message.content.text
                    text = getattr(content, "text", None)
                    if text is None:
                        # fallback: serializuj neznámou strukturu
                        text = json.dumps(content, ensure_ascii=False)
            except Exception:
                text = str(message)
            if text:
                parts.append(text)

        query = "\n".join(parts).strip()

        # 4) Info zprávy, pokud nepřepisujeme system prompt (tj. „ptám se sám sebe“)
        # if system_prompt is None:
        #     await onMessage("Musím se zeptat sám sebe")
        #     await onMessage(query)

        # 5) Udrž historie krátkou (pokud máme reuse session)
        try:
            currentChatSession._trim_history()
        except Exception:
            pass

        # 6) Zavolej LLM
        try:
            llm_response = await currentChatSession.ask(
                query,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            err = f"Chyba při dotazu na LLM: {e}"
            onLog(err)
            if system_prompt is None:
                await onMessage(err)
            raise

        # 7) Log/echo
        # if system_prompt is None:
        #     await onMessage(
        #         "Odpovídám si \n\n"
        #         "```json\n"
        #         f"{llm_response}"
        #         "\n```"
        #     )

        onLog(
            "Ptám se LLM \n\n"
            "```json\n"
            f"{query}"
            "\n```"
        )
        onLog(
            "LLM mi odpovídá \n\n"
            "```json\n"
            f"{llm_response}"
            "\n```"
        )

        print(f"onSampling {messages}, {params}")
        return llm_response

    return onSampling    

def ComponentTextContent(
    textContent: TextContent
):
    return ui.markdown(
        content=textContent.text
    )

ComponentIndex = {
    # "graphql": GraphQLData,
    "text": ComponentTextContent,
}

@ui.page("/")
async def index_page():
    chatSession = ChatSession()
    mcpClient = fastmcp.Client(MCPURL)
    from main_mcp import createGQLClient
    gqlClient = await createGQLClient(
        username="john.newbie@world.com",
        password="john.newbie@world.com"
    )

    async with mcpClient:
        # result["tool.response"] = await client.call_tool("echo", {"text": "hello"})
        mcp_tools = await mcpClient.list_tools()
        prompts = await mcpClient.list_prompts()
        print(f"mcp tools: {mcp_tools}")
        print(f"mcp prompts: {prompts}")
        
    
    #     resources = await client.list_resource_templates()
        
    #     # Filter resources by tag
    #     result["config_resources"] = [
    #         resource for resource in resources 
    #         # if hasattr(resource, '_meta') and resource._meta and
    #         #     resource._meta.get('_fastmcp', {}) and
    #         #     'config' in resource._meta.get('_fastmcp', {}).get('tags', [])
    #     ]        
    # return result
    # https://github.com/zauberzeug/nicegui/blob/main/examples/chat_with_ai/main.py

    # print("Index page", type(request), type(response), type(unknown))
    # ui.label("Hello, World!")
    # ui.button("Click me", on_click=lambda: ui.notify("Clicked!"))
    async def addAssistantMsg(msg):
        with message_container:
            response_message = ui.chat_message(name='Radílek', sent=False).classes("no-tail").props('bg-color=grey-8 text-color=black')    
            # response_message = ui.chat_message(name='Radílek', sent=False).classes("no-tail")
            with response_message:
                # ui.html(part["content"])
                with ui.element('div').classes('table-responsive'):
                    ui.markdown(msg)
        return response_message

    async def addUserMsg(msg):
        with message_container:
            response_message = ui.chat_message(name='You', sent=True).classes("no-tail")
            with response_message:
                # ui.html(part["content"])
                ui.markdown(msg)
        return response_message

    async def send(e: nicegui.events.GenericEventArguments) -> None:
        if e.args['shiftKey']:
            return 
        
        question = text.value
        text.value = ''
        with message_container:
            ui.chat_message(text=question, name='You', sent=True).classes("no-tail")

            onSampling = createOnSample(
                chatSession=chatSession,
                onMessage=addAssistantMsg,
                onLog=lambda msg: log.push(msg)
            )

            async def onProgress(
                progress: float, 
                total: float | None, 
                message: str | None
            ):
                await addAssistantMsg(f"{message}")
                await chatSession.append_history(
                    {"role": "assistant", "content": message}
                )
                pass

            async with fastmcp.Client(
                MCPURL,
                sampling_handler=onSampling,
                progress_handler=onProgress
            ) as mcpClient:
                router = MCPRouter(mcpClient=mcpClient)
                # await addUserMsg(question)
                await chatSession.append_history(
                    {"role": "user", "content": question}
                )

                @router.filter(filter_type=FilterType.ROUTE_ERROR)
                async def route_error_log(ctx: RouterContext, next):
                    log.push((
                        "[ROUTE_ERROR]\n"
                        f'{ctx.meta.get("router_last_error")}'
                    ))
                    print("[ROUTE_ERROR]", ctx.meta.get("router_last_error"))
                    # tady můžeš poslat metriky do APM / OpenTelemetry
                    return await next()

                @router.filter(filter_type=FilterType.ROUTE_ERROR)
                async def route_tool_select(ctx: RouterContext, next):
                    log.push((
                        "[ROUTE_SELECT]\n"
                        f"{ctx.selected_tool}"
                    ))
                    return await next()

                tools = [tool.model_dump() for tool in mcp_tools]

                context = RouterContext(
                    user_message=question,
                    tools_json=tools
                )
                # print(f"niceguid.page.tools {tools}")
                try:
                    context_result: RouterContext = await router.route_and_call(
                       context=context 
                    )
                    if tool_response := context_result.result:

                        if tool_response_content := tool_response.content:
                            for content_block in tool_response_content:
                                Component = ComponentIndex.get(
                                    content_block.type
                                )
                                if Component:
                                    with message_container:
                                        Component(content_block)

                        if tool_response.structured_content is not None:
                            graphql = tool_response.structured_content.get("graphql")
                            if graphql is not None:
                                with message_container:
                                    GraphQLData(
                                        gqlclient=gqlClient, 
                                        query=graphql.get("query"),
                                        variables=graphql.get("variables"),
                                        result=graphql.get("result"),
                                        metadata=tool_response.structured_content,
                                        autoload=False
                                    )
                            else:
                                await addAssistantMsg((
                                    "## Odpověď (structured_content) jako json\n\n"
                                    "```json\n"
                                    f"{json.dumps(tool_response.structured_content, indent=2, ensure_ascii=False)}"
                                    "\n```"
                                ))

                    
                        
                    elif direct_response := context_result.meta.get("router_final_answer"):
                        await addAssistantMsg((
                            f"{direct_response}"
                            "\n"    
                        ))
                    elif question_for_user := context_result.meta.get("router_question"):
                        await addAssistantMsg((
                            f"{question_for_user}"
                            "\n"    
                        ))
                    else:
                        await addAssistantMsg((
                            "Neco je fakt spatne\n\n"
                            "```json\n"
                            f"{json.dumps(context_result.meta, indent=2, ensure_ascii=False)}"
                            "\n```\n"
                        ))
                except Exception as e:
                    await addAssistantMsg((
                        f"Doslo k chybe pri volani nastroje {context.attempt}" 
                        "\n\n"
                        f"{context.error}"
                        "\n"
                        f"{type(e)} {e}"
                        f"{exception_to_markdown(e)}"
                    ))
                
        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

        # text.value = ''
        


    ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
    ui.add_head_html("""
    <style>
    /* bloky kódu z trojitých backticků */
    .q-message .markdown pre {
    background: #f6f8fa;       /* světlé pozadí pro čitelnost */
    color: inherit;
    padding: 12px;
    border-radius: 8px;
    overflow: auto;
    box-shadow: inset 0 0 0 1px rgba(0,0,0,.04);
    }
    /* inline `code` */
    .q-message .markdown code:not(pre code) {
    background: rgba(0,0,0,.06);
    padding: .15em .35em;
    border-radius: 4px;
    }
    /* ať se nenasčítají pozadí u pre > code */
    .q-message .markdown pre code {
    background: transparent;
    padding: 0;
    }
    </style>
    """)    

    ui.add_head_html("""
    <style>
    /* Bootstrap-like responsive wrapper */
    .table-responsive {
    display: block;
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    }
    /* optional: aby se tabulka nerozpadala a nevylézala z bubliny */
    .table-responsive table {
    margin-bottom: 0;
    border-collapse: collapse;
    }
    .table-responsive th, 
    .table-responsive td {
    /* buď nech svinování textu... */
    white-space: nowrap;      /* ← zruš, pokud chceš zalamovat */
    /* ...a nebo povol zalamování:
    white-space: normal;
    word-break: break-word;
    */
    }
    </style>
    """)    
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
            # ui.chat_message(text="I have arrived", name='You', sent=True).classes("no-tail")
            ui.chat_message(
                text="Zdravím! Jak Ti mohu pomoci?", 
                name='Radílek', 
                sent=False
            ).classes("no-tail")
            # ui.markdown("""
            #             # My response
            #             ```json
            #             {
            #                 "question": "{question}"
            #             }
            #             ```
            #             """
            #             """I have responded to {question}""")
            
            # ui.chat_message(text="Hi! How can I help you?", name='Radílek', sent=False)
        with ui.tab_panel(logs_tab):
            log = ui.log().classes('w-full h-full') 

    with ui.footer().classes("bg-gray-600"), ui.column().classes('w-full max-w-3xl mx-auto my-6'):
        with ui.row().classes('w-full no-wrap items-center'):
            placeholder = ("message" 
                # if "OPENAI_API_KEY" != 'not-set' else \
                # 'Please provide your OPENAI key in the Python script first!'
            )
            # text = ui.input(label="User query", placeholder=placeholder).props('rounded outlined input-class mx-3') \
            #     .classes('w-full self-center').on('keydown.enter', send)
            text = (
                ui.textarea(label="User query", placeholder=placeholder)
                .props('rounded outlined input-class mx-3') \
                .classes('w-full self-center')
                .on('keydown.enter', send)
            )

# endregion


"""
navrhni mi formular pro zadost studenta s polozkami
- jmeno a prijmeni studenta
- zneni zadosti
- vyjadreni nekolika osob k zadosti
    - kdo se vyjadril
    - jake vyjadreni napsal
"""

"""
vrat mi seznam uzivatelu se jmenem Petr
"""