import json
import typing
import fastmcp

from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import SamplingMessage

from ..mcpserver import mcp, createGQLClient
from ..resources import get_graphql_types, build_graphql_query_nested
from ..prompts import pickup_graphql_types, get_build_form

@mcp.tool(
    description=(
        "Returns complete list of availlable graphql types from graqphql endpoint with description. "
        "This allows to derive which types the user is talking about."
    )
)
async def get_complete_gql_types_list(
    ctx: fastmcp.Context
):
    result = await get_graphql_types.fn(ctx)
    return result

@mcp.tool(
    description=(
        "Returns a graphql query base on required graphql types with rich description of use. "
    )
)
async def get_query_for_types(
    types: typing.Annotated[
        str,
        (
            "list of graphql types delimited by comma",
            "An example is \n\n"
            "UserGQLModel,GroupGQLModel"
        )
    ],
    ctx: fastmcp.Context
):
    l_types = types.split(',')
    t_types = "/".join(
        [
            t_str.strip()
            for t_str in l_types
        ]
    )
    query = await build_graphql_query_nested.fn(
        types=t_types,
        ctx=ctx
    )
    return query
    


@mcp.tool(
    description=(
        "Asks graphql endpoint for data. "
        "If the query is known this is appropriate tool for extraction data from graphql endpoint. "
        "Data are returned as markdown table."
    ),
    tags={"graphql"}
)
async def ask_graphql_endpoint(
    query: typing.Annotated[str, "graphql query"],
    variables: typing.Annotated[dict, "variables for the graphql query"],
    # query: str,
    # variables: dict,
    ctx: fastmcp.Context
) -> ToolResult:
    gqlClient = ctx.get_state("gqlClient")
    if gqlClient is None:
        gqlClient = await createGQLClient(
            username="john.newbie@world.com",
            password="john.newbie@world.com"
        )
        ctx.set_state(
            key="gqlClient",
            value=gqlClient
        ) 

    response_data_set = await gqlClient(query=query, variables=variables)
    response_errors = response_data_set.get("errors") 
    # assert response_errors is None, f"During query {query} got response {response_data_set}"
    if response_errors is not None:
        return ToolResult(
            content=TextContent(
                type="text",
                text=f"During query {query} got response with errors {response_data_set}"
            ),
            structured_content={
                "sourceid": "9e3ab68d-a166-416c-941c-8eb1a87c728f",
                "errors": response_errors
            }
        )
    response_data = response_data_set.get("data")
    # assert response_data is not None, "Probably the graphql endpoint is not running"
    if response_data is None:
        return ToolResult(
            content=TextContent(
                type="text",
                text=f"Probably the graphql endpoint is not running"
            ),
            structured_content={
                "sourceid": "b40aa51b-4013-426b-989d-4748bc8b55a6",
                "errors": f"Probably the graphql endpoint is not running"
            }
        )
    print(f"response_data: {response_data}")
    data_list = next(iter(response_data.values()), None)
    print(f"data_list: {data_list}")
    # assert data_list is not None, f"Cannot found expected list of entities in graphql response {response_data_set}"
    if data_list is None:
        return ToolResult(
            content=TextContent(
                type="text",
                text=f"Cannot found expected list of entities in graphql response {response_data_set}"
            ),
            structured_content={
                "sourceid": "8fdeb496-9612-4067-a08d-f77126c81e50",
                "errors": f"Cannot found expected list of entities in graphql response {response_data_set}"
            }
        )
    md_table = await display_list_of_dict_as_table.fn(
        data=data_list,
        ctx=ctx
    )
    return ToolResult(
        content=TextContent(
            type="text",
            text=md_table
        ),
        structured_content={
            "sourceid": "0d5febef-6fc3-4648-a255-640332bf4df2",
            "response": md_table,
            "graphql": {
                "query": query,
                "variables": variables,
                "result": response_data
            }
        }
    )

    

@mcp.tool(
    description="Retreieves data from graphql endpoint. If the user want to get some data or entities this is appropriate tool to run.",
    tags={"graphql"}
)
async def get_graphQL_data(
    user_message: str, 
    ctx: fastmcp.Context
) -> ToolResult:
    import json
    import graphql
    print(f"get_graphQL_data.client_id[{ctx.client_id}]")
    print(f"get_graphQL_data.request_id[{ctx.request_id}]")
    print(f"get_graphQL_data.session_id[{ctx.session_id}]")
    # gqlClient = await createGQLClient(
    #     username="john.newbie@world.com",
    #     password="john.newbie@world.com"
    # )

    # # sdl analysis
    # sdl_query = "query __ApolloGetServiceDefinition__ { _service { sdl } }"
    # response = await gqlClient(query=sdl_query)
    # response_data = response.get("data")
    # assert response_data is not None, "Probably the graphql endpoint is not running"
    # _service = response_data.get("_service")
    # assert _service is not None, "Something went wrong, this could be error in code. _service key in graphql response is missing"
    # sdl_str = _service.get("sdl")
    # assert sdl_str is not None, "Something went wrong, this could be error in code. sdl key in graphql response is missing"
    # sdl_ast = graphql.parse(sdl_str)

    # sdl_ast = get_graphql_sdl.fn(ctx)
    # types and its description extraction

    availableGQLTypes = await get_graphql_types.fn(ctx)

    # sdl_ast = ctx.get_state("sdl_ast")
    gqlClient = ctx.get_state("gqlClient")
    assert gqlClient is not None, f"ctx.state does not contains gqlClient, that is code error"
    print(f"get_graphQL_data.availableGQLTypes: {availableGQLTypes[:2]} ...")
    
    prompt = await pickup_graphql_types.fn(
        user_prompt=user_message,
        ctx=ctx
    )

    # dotaz (callback / mcp.sample) na LLM pro vyber dotcenych typu
    
    llmresponse = await ctx.sample(messages=prompt)
    # llmresponse = await fallback_sample(messages=prompt)
    print(f"get_graphQL_data.llmresponse: {llmresponse.text}")
    type_list = json.loads(llmresponse.text)

    assert isinstance(type_list, list), (
        "Unable to get related graphql types.\n"
        f"{llmresponse.text}"
    )
    assert len(availableGQLTypes) > 0, (
        "The list of recognized graphql types is empty.\n"
        f"{json.dumps(availableGQLTypes, indent=2)}"
    )

    query = await build_graphql_query_nested.fn(
        types="/".join(type_list),
        ctx=ctx
    )
    
    def take(query):
        for row in query.split("/n"):
            if row.startswith("# @returns"):
                return
            yield row
    
    variables = {}
    # InputDefinitions = [row for row in take(query)]
    # filter_recognition = await ctx.sample(
    #     messages= (
    #         "Schema and filter rules of input variables of graphql query\n\n"
    #         f"{InputDefinitions}"
    #         "\n\n"
    #         "given user query\n"
    #         f"{user_message}"
    #     ),
    #     system_prompt=(
    #         "You are a converter from natural language to GraphQL variable JSON.\n"
    #         "Your ONLY OUTPUT must be one JSON object for the GraphQL variables.\n"
    #         "Omit any envelope or ticks like ' or ```.\n"
    #     )

    # )
    # print("get_graphql_data")
    # print(f"{filter_recognition}")
    # variables = json.loads(filter_recognition.text)

    await ctx.report_progress(
        progress=50,
        total=100,
        message=(
            "### Dotaz na GQL endpoint\n\n"
            "```gql\n"
            f"{query}"
            "\n```"
        )
    )
    response_data_set = await gqlClient(query=query, variables=variables)
    response_error = response_data_set.get("errors") 
    assert response_error is None, f"During query {query} got response {response_data_set}"
    response_data = response_data_set.get("data")
    assert response_data is not None, "Probably the graphql endpoint is not running"
    # print(f"response_data: {response_data}")
    data_list = next(iter(response_data.values()), None)
    # print(f"data_list: {data_list}")
    assert data_list is not None, f"Cannot found expected list of entities in graphql response {response_data_set}"
    md_table = await display_list_of_dict_as_table.fn(
        data=data_list,
        ctx=ctx
    )
    return ToolResult(
        content=TextContent(
            type="text",
            text=md_table
        ),
        structured_content={
            "sourceid": "9d5e6b6b-4e87-4cc6-872d-9a7083574dfe",
            "graphql": {
                "query": query,
                "variables": variables,
                "result": response_data
            }
        }
    )
    


@mcp.tool(
    description="transforms the list of dict into table represented as a markdown fragment",
    tags={"ui"}
)
async def display_list_of_dict_as_table(data: typing.List[typing.Dict], ctx: fastmcp.Context) -> str:
    if not data:
        return "*(no data)*"

    # Sloupce vezmeme z klíčů prvního dictu
    headers = [key for key, value in data[0].items() if not isinstance(value, (dict, list))]

    # Hlavička
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join("---" for _ in headers) + " |"

    # Řádky
    rows = []
    for item in data:
        row = "| " + " | ".join(str(item.get(col, "")) for col in headers) + " |"
        rows.append(row)

    # Spojení všeho
    return "\n".join([header_line, separator_line] + rows)

@mcp.tool(
    description="From user message creates json describing the wanted form"
)
async def build_form(
    user_message: str, 
    ctx: fastmcp.Context
) -> ToolResult:
    prompt = await get_build_form.fn(
        # user_prompt=user_message,
        # ctx=ctx
    )

    # dotaz (callback / mcp.sample) na LLM pro vyber dotcenych typu
    messages=[
            prompt,
            "\n\nUser message:\n\n"
            f"{user_message}"
    ]
    llmresponse = await ctx.sample(messages=messages)
    # llmresponse = await fallback_sample(messages=messages)
        
    print(f"build_form.llmresponse: {llmresponse}")
    form_definition = json.loads(llmresponse.text)
    return ToolResult(
        content=TextContent(
            type="text",
            text=(
                "```json\n"
                f"{llmresponse.text}"
                "\n```"
            )
        ),
        structured_content={
            "sourceid": "6e183e14-1c4e-490d-a693-8b59e6c050ea",
            "form": form_definition
        }
    )


@mcp.tool(
    description="This tool allows to define which application the user want to open"
)
async def choose_link(
    query: str,
    top_k: int = 3,
    # base_url: str | None = None,
    ctx: fastmcp.Context | None = None
):
    from ..prompts import link_prompt
    top_k = max(1, min(int(top_k), 10))

    messages = await link_prompt.fn(query, top_k=top_k)

    print(f"messages: {json.dumps(messages, indent=2, ensure_ascii=False)}")
    message_f = [
        SamplingMessage(**m) for m in messages
    ]
    for message in messages:
        print(f"{type(message)}: {json.dumps(message)}")
    sample_res_str = await ctx.sample(
        messages=messages,
        temperature=0.2
    )    
    # sample_res_str = await fallback_sample(
    #     messages=messages,
    #     temperature=0.2
    # )    
    result = json.loads(sample_res_str.text)
    return ToolResult(
        content=TextContent(
            type="text",
            text=(
                "## Odpověď\n\n"
                "```json\n"
                f"{json.dumps(result, indent=2)}"
                "\n```\n"
            )
        ),
        structured_content={
            "raw": result
        }
    )
    pass
