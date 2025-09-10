import fastmcp

from ..mcpserver import mcp

@mcp.resource(
    description="extract sdl of the graphql endpoint",
    uri="resource://graphql/sdl",
    mime_type="application/json", # Explicit MIME type
    tags={"metadata"}, # Categorization tags
)
async def get_graphql_sdl(ctx: fastmcp.Context):
    import graphql
    from ..mcpserver import createGQLClient
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
    sdl_query = "query __ApolloGetServiceDefinition__ { _service { sdl } }"
    response = await gqlClient(query=sdl_query)
    response_data = response.get("data")
    assert response_data is not None, "Probably the graphql endpoint is not running"
    _service = response_data.get("_service")
    assert _service is not None, "Something went wrong, this could be error in code. _service key in graphql response is missing"
    sdl_str = _service.get("sdl")
    assert sdl_str is not None, "Something went wrong, this could be error in code. sdl key in graphql response is missing"
    sdl_ast = graphql.parse(sdl_str)
    ctx.set_state(
        key="sdl_ast",
        value=sdl_ast
    )
    print(f"get_graphql_sdl - set sdl_ast to {sdl_ast}")
    return sdl_ast


@mcp.resource(
    description="returns a list of types at graphql endpoint paired with their description",
    uri="resource://graphql/types",
    mime_type="application/json", # Explicit MIME type
    tags={"metadata"}, # Categorization tags
)
async def get_graphql_types(ctx: fastmcp.Context):
    import graphql
    sdl_ast = ctx.get_state("sdl_ast")
    if sdl_ast is None:       
        sdl_ast = await get_graphql_sdl.fn(ctx)
        print(f"get_graphql_types.sdl_ast = {sdl_ast}")
        
    result = {}
    for node in sdl_ast.definitions:
        if isinstance(node, graphql.language.ast.ObjectTypeDefinitionNode):
            name = node.name.value
            if "Error" in name:
                continue
            description = node.description.value if node.description else None
            result[name] = {"name": name, "description": description}

    result = list(result.values())
    return result


@mcp.resource(
    description=(
        "This resource generates a GraphQL query from an ordered list of types. "
        "The query's root selects the first type; "
        "subsequent levels progressively nest selections to reach each following type in sequence. "
        "If necessary, the generator inserts implicit intermediate types that link the specified types, "
        "even when those intermediates were not explicitly provided."
    ),
    uri="resource://graphql/query/{types*}",
)
async def build_graphql_query_nested(
    types: str,
    ctx: fastmcp.Context
):
    print(f"build_graphql_query_nested: {types}")
    typeslist = types.split("/")
    from src.Utils.GraphQLQueryBuilder import GraphQLQueryBuilder
    sdl_ast = await get_graphql_sdl.fn(ctx)
    querybuilder = GraphQLQueryBuilder(
        sdl_ast=sdl_ast,
        disabled_fields=[
            "createdby",
            "changedby"
        ]
    )
    query = querybuilder.build_query_vector(
        types=typeslist
    )
    from src.Utils.explain_query import explain_graphql_query
    query = explain_graphql_query(
        schema_ast=sdl_ast,
        query=query
    )
    return query
