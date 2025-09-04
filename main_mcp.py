import typing
import json

# region mcp
import fastmcp
from fastmcp import FastMCP, Client
from fastmcp.tools.tool import ToolResult, TextContent

# MCP server instance
mcp = FastMCP("My MCP Server")

# Definice toolu
# @mcp.tool(
#     description="return the given text back"
# )
# def echo(text: str, ctx: fastmcp.Context) -> str:
#     """Return the same text back."""
#     return text

# @mcp.resource(
#     uri="resource://{name}/page",
#     mime_type="application/json", # Explicit MIME type
#     tags={"data"}, # Categorization tags
#     meta={"version": "2.1", "team": "infrastructure"}  # Custom metadata
# )
# async def get_details(name: str, ctx: fastmcp.Context) -> dict:
#     """Get details for a specific name."""
#     return {
#         "name": name,
#         "accessed_at": ctx.request_id
#     }

# @mcp.prompt
# def ask_about_topic(topic: str, ctx: fastmcp.Context) -> str:
#     """Generates a user message asking for an explanation of a topic."""
#     return f"Can you please explain the concept of '{topic}'?"

@mcp.prompt(
    description="builds system prompt for appropriate tool selection",
    # uri="prompt://recognizetool"
)
async def get_use_tools(tools: list[dict]) -> str:
    
    toolsstr = json.dumps(tools, indent=2)
#     prompt = ("""
# # Instructions
              
# Choose if a tool defined by mcp server will be called or you can respond to user query.
# You can either answer directly or call exactly one tool.
                    
# ## Responses
              
# If you suggest to call the tool, the response must be in form             

# {"action":"tool", "tool":"here place the picked tool name", "arguments": {...} }

# otherwise return your answer in form

# {"action":"respond", "message": "..."}

# Response must be in valid JSON, so it can be directly used to load json from string
              
# ## Available tools
              
# """
              
# "```json\n"
# f"{toolsstr}"
# "\n```"
      
#     )
    prompt = (
 "You can either answer directly or call exactly one tool.\n"
        "Respond in JSON only.\n"
        "Schema:\n"
        '{"action":"respond","message":"..."}\n'
        "or\n"
        '{"action":"tool","tool":"NAME","arguments":{...}}\n\n'
        "Available tools:\n\n"
        f"{tools}"    )
    prompt = (
        """You are an API that must respond **only in valid JSON**, never plain text.

You have exactly two options for output schema (choose one):

1. Respond directly:
   {"action": "respond", "message": "<plain natural language answer>"}

2. Call exactly one tool:
   {"action": "tool", "tool": "<TOOL_NAME>", "arguments": { ... }}

Rules:
- Output must be valid JSON, no extra text or Markdown fences.
- Choose at most one tool.
- If unsure, prefer {"action":"respond",...}.
- Do not invent tools beyond those listed.

Examples:

Q: "Explain what GraphQL is."
A: {"action":"respond","message":"GraphQL is a query language for APIs that lets clients specify exactly the data they need."}

Q: "Give me all users from the endpoint"
A: {"action":"tool","tool":"getgraphQLdata","arguments":{"usermessage":"Give me all users"}}

Available tools:

"""
f"{tools}" 
    )
    return prompt


@mcp.prompt(
    description="build system prompt for graphql filter construction from well known graphql query string with comments"
)
async def get_build_filter(graphQuery: str) -> str:
    headerLines = []
    for line in graphQuery:
        if line.startswith("# @returns"):
            break
        headerLines.append(line)

    "\n".join(headerLines)

    return (
        """
You are a GraphQL filter extractor. 
Your task: from USER_QUERY produce ONLY a strict JSON object with keys { "skip", "limit", "orderby", "where" }.
No prose, no comments, no trailing commas. If a key is unknown, still output it with a sensible default.

CONTEXT
- GraphQL pagination & sorting:
  - skip: Int (default {{SKIP_DEFAULT}})
  - limit: Int (default {{LIMIT_DEFAULT}}, clamp to [1, {{LIMIT_MAX}}])
  - orderby: String (default "{{ORDERBY_DEFAULT}}"); examples: "name ASC", "startdate DESC"

- allowed operators for types:
  - UUID:      {_eq: UUID}, {_in: [UUID, ...]}
  - Str:       {_eq, _ge, _gt, _le, _lt, _like, _startswith, _endswith}
  - Bool:      {_eq: true|false}
  - DateTime:  {_eq, _le, _lt, _ge, _gt}   // ISO 8601, e.g. "2025-06-30T18:01:59"
  - Object:    (compound subfilter using the same operators on its fields, e.g. {"grouptype": {"name_en": {"_like": "%research%"}}})

- Logical composition constraints:
  - Subfilters can be nested via `_and` and `_or`.
  - `_and` can nest only `_or`, while `_or` can nest only `_and`.
  - `_and` is a list: ALL must be satisfied. `_or` is a list: ANY can be satisfied.
  - Always respect the alternating pattern when nesting.

- Time & locale:
  - NOW (local to user) is {{NOW_ISO}} in ISO 8601 (e.g. "2025-09-02T10:00:00").
  - Interpret phrases like "aktuální/platné teď/today/now" as:
      startdate <= NOW AND enddate >= NOW   (enforced via the allowed operators).
  - "posledních N let/měsíců/dnů" → use relative window against NOW (e.g., startdate >= NOW minus N*unit).
    Emit concrete ISO timestamps (no words like "NOW-5Y").

- Text matching:
  - Use only the listed operators. For contains semantics, prefer `_like` with `%...%`.
  - If the user gives multi-language keywords, you may OR-combine `name` and `name_en`.

- Safety & bounds:
  - Do NOT invent fields not listed above.
  - If the user supplies explicit JSON for `where`, normalize but keep semantics.
  - If the query lacks constraints, ommit `where` completely.

- Defaults (if unspecified):
  - skip = {{SKIP_DEFAULT}}
  - limit = {{LIMIT_DEFAULT}}
  - orderby = "{{ORDERBY_DEFAULT}}"
  - where = {}

MAPPING HINTS (examples):
- "aktuální/platné teď" → startdate <= NOW AND enddate >= NOW
- "ID je ..." → id._eq; "ID je v seznamu" → id._in
- "grouptype je ..." (UUID) → grouptype_id._eq; textově → grouptype.name/_name_en with string ops
- "patří pod ..." (UUID) → mastergroup_id._eq
- "název obsahuje X" → name._like "%X%"
- "za posledních 5 let" → startdate._ge {{ISO_YEARS_AGO(5)}}

OUTPUT FORMAT (MANDATORY):
Return only:
{
  "skip": Int,
  "limit": Int,
  "orderby": "String",
  "where": { ...InputWhereFilter... }
}

FEW-SHOT

USER_QUERY:
"Najdi aktuální skupiny související s kvantem nebo operačním výzkumem, seřaď od nejnovějších, limit 20."
OUTPUT:
{
  "skip": 0,
  "limit": 20,
  "orderby": "startdate DESC",
  "where": {
    "_and": [
      { "startdate": { "_le": "{{NOW_ISO}}" } },
      { "_or": [
          { "_and": [ { "enddate": { "_ge": "{{NOW_ISO}}" } } ] }
        ]
      },
      { "_or": [
          { "_and": [ { "name": { "_like": "%kvant%" } } ] },
          { "_and": [ { "name_en": { "_like": "%quantum%" } } ] },
          { "_and": [ { "name_en": { "_like": "%operations research%" } } ] }
        ]
      }
    ]
  }
}

USER_QUERY:
"Skupiny podle grouptype_id 5fa97795-454e-4631-870e-3f0806018755 nebo 011ec2bc-a0b9-44f3-bcd8-a42691eebaa4, jméno začíná na 'Def'. Limit 50, přeskoč 100."
OUTPUT:
{
  "skip": 100,
  "limit": 50,
  "orderby": "name ASC",
  "where": {
    "_and": [
      { "_or": [
          { "_and": [ { "grouptype_id": { "_in": ["5fa97795-454e-4631-870e-3f0806018755", "011ec2bc-a0b9-44f3-bcd8-a42691eebaa4"] } } ] }
        ]
      },
      { "_or": [
          { "_and": [ { "name": { "_startswith": "Def" } } ] },
          { "_and": [ { "name_en": { "_startswith": "Def" } } ] }
        ]
      }
    ]
  }
}

USER_QUERY:
"ID = aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OUTPUT:
{
  "skip": {{SKIP_DEFAULT}},
  "limit": {{LIMIT_DEFAULT}},
  "orderby": "{{ORDERBY_DEFAULT}}",
  "where": {
    "_and": [
      { "_or": [
          { "_and": [ { "id": { "_eq": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" } } ] }
        ]
      }
    ]
  }
}

QUERY_PARAMETERS_DEFINITION:
"""

        f"{headerLines}"
    )

@mcp.prompt(
    description="build system prompt for construction of json datastructure describing the digital form"
)
async def get_build_form() -> str:
    prompt = (
        """
You are a compiler from free-form user requirements into a STRICT JSON object matching the GraphQL input model DigitalFormInsertGQLModel.
Return ONLY JSON. No comments, no prose, no trailing commas.

### Objective
From USER_REQUEST produce a single JSON object compatible with mutation input:
DigitalFormInsertGQLModel {
  name: String|null
  nameEn: String|null
  id: UUID|null                 // client-generated
  sections: [DigitalFormSectionInsertGQLModel!]
}

DigitalFormSectionInsertGQLModel {
  name: String|null
  label: String|null
  labelEn: String|null
  sectionId: UUID|null          // parent section uuid if provided
  formId: UUID|null             // form uuid if provided
  id: UUID|null                 // client-generated
  repeatableMin: Int|null
  repeatableMax: Int|null
  repeatable: Boolean           // default false
  fields: [DigitalFormFieldInsertGQLModel!]
  sections: [DigitalFormSectionInsertGQLModel!]
}

DigitalFormFieldInsertGQLModel {
  formId: UUID|null
  typeId: UUID|null             // must come from a known mapping or remain null
  formSectionId: UUID|null
  id: UUID|null                 // client-generated
  name: String|null             // variable name
  label: String|null
  labelEn: String|null
  description: String|null
  required: Boolean             // default false
  order: Int                    // default 0 (auto-increment if unspecified)
  computed: Int|null            // expression identifier or null
}

### Constraints & Defaults
- Output must be valid JSON for the above shape.
- Omit unknown fields; never invent schema keys.
- Defaults:
  - sections, fields default to empty arrays [].
  - repeatable default false; repeatableMin/Max null unless specified or implied.
  - required default false.
  - order default 0; if multiple fields in a section lack order, assign 1..N in declaration order.
- IDs:
  - If user provides IDs, keep them.
  - If IDs are missing and client-side IDs are desired, set:
      id = {{GENERATE_UUID()}}
    Else set null. (Server will substitute if it supports generation.)
  - Do NOT fabricate formId/sectionId/formSectionId; set them from user input if given.
    If nesting is used without explicit FKs, leave these FKs null.
- Names:
  - If a section/field has label but no name, derive `name` by slugifying the label:
      lowerCamelCase, ASCII-only, no spaces, remove diacritics.
      Ensure uniqueness within the same scope by suffixing _2, _3, ...
- Language:
  - If the user provides both CZ and EN texts, map to label/labelEn (and name/nameEn for form).
  - If only one language is present, fill the corresponding field and leave the other null.
- Booleans:
  - Map phrases like ["povinné", "required", "mandatory"] → required=true.
  - Map ["opakovatelná sekce", "repeatable"] → repeatable=true; try to parse min/max if stated.
- Field types:
  - Map textual types (e.g., "text", "number", "date", "email", "select") to typeId via:
      {{FIELD_TYPE_MAP_JSON}}
    If mapping missing, leave typeId=null.
- Computed:
  - If user describes a computed field (formula/rule), set `computed` to an integer code if provided,
    otherwise leave null (do not invent computation).
- Validation:
  - If repeatable=false, ignore repeatableMin/Max (set null).
  - If repeatable=true and only one bound present, set the other bound null.
  - Ensure arrays are arrays even if single item is specified.
- Safety:
  - If USER_REQUEST is ambiguous, pick the most conservative interpretation (fewer assumptions).
  - Never include explanations; output JSON only.

### Output format (MANDATORY)
Return exactly one JSON object of shape DigitalFormInsertGQLModel.
Example skeleton (not a template):
{
  "name": "...",
  "nameEn": null,
  "id": null,
  "sections": [ /* DigitalFormSectionInsertGQLModel */ ]
}

### FEW-SHOT EXAMPLES

USER_REQUEST:
"Vytvoř formulář 'Žádost o dovolenou' / EN 'Leave Request'. Sekce 'Základní údaje' s poli:
- Jméno (text, povinné)
- Datum od (date, povinné)
- Datum do (date, povinné)
Sekce 'Detaily' opakovatelná min 1 max 3 s polem 'Poznámka' (textarea, nepovinné)."

AUX:
{{FIELD_TYPE_MAP_JSON}} = {"text":"11111111-1111-1111-1111-111111111111","date":"22222222-2222-2222-2222-222222222222","textarea":"33333333-3333-3333-3333-333333333333"}
{{GENERATE_UUID()}} returns a UUIDv7 string

OUTPUT:
{
  "name": "zadostODovolenou",
  "nameEn": "leaveRequest",
  "id": {{GENERATE_UUID()}},
  "sections": [
    {
      "name": "zakladniUdaje",
      "label": "Základní údaje",
      "labelEn": null,
      "sectionId": null,
      "formId": null,
      "id": {{GENERATE_UUID()}},
      "repeatableMin": null,
      "repeatableMax": null,
      "repeatable": false,
      "fields": [
        {
          "formId": null,
          "typeId": "11111111-1111-1111-1111-111111111111",
          "formSectionId": null,
          "id": {{GENERATE_UUID()}},
          "name": "jmeno",
          "label": "Jméno",
          "labelEn": null,
          "description": null,
          "required": true,
          "order": 1,
          "computed": null
        },
        {
          "formId": null,
          "typeId": "22222222-2222-2222-2222-222222222222",
          "formSectionId": null,
          "id": {{GENERATE_UUID()}},
          "name": "datumOd",
          "label": "Datum od",
          "labelEn": null,
          "description": null,
          "required": true,
          "order": 2,
          "computed": null
        },
        {
          "formId": null,
          "typeId": "22222222-2222-2222-2222-222222222222",
          "formSectionId": null,
          "id": {{GENERATE_UUID()}},
          "name": "datumDo",
          "label": "Datum do",
          "labelEn": null,
          "description": null,
          "required": true,
          "order": 3,
          "computed": null
        }
      ],
      "sections": []
    },
    {
      "name": "detaily",
      "label": "Detaily",
      "labelEn": null,
      "sectionId": null,
      "formId": null,
      "id": {{GENERATE_UUID()}},
      "repeatableMin": 1,
      "repeatableMax": 3,
      "repeatable": true,
      "fields": [
        {
          "formId": null,
          "typeId": "33333333-3333-3333-3333-333333333333",
          "formSectionId": null,
          "id": {{GENERATE_UUID()}},
          "name": "poznamka",
          "label": "Poznámka",
          "labelEn": null,
          "description": null,
          "required": false,
          "order": 1,
          "computed": null
        }
      ],
      "sections": []
    }
  ]
}

USER_REQUEST:
"Formulář 'Incident Report' (EN). Jedna sekce 'Event' s poli: Title (text, required), Occurred At (date), Description (textarea)."

AUX:
{{FIELD_TYPE_MAP_JSON}} = {"text":"11111111-1111-1111-1111-111111111111","date":"22222222-2222-2222-2222-222222222222","textarea":"33333333-3333-3333-3333-333333333333"}

OUTPUT:
{
  "name": "incidentReport",
  "nameEn": "incidentReport",
  "id": null,
  "sections": [
    {
      "name": "event",
      "label": "Event",
      "labelEn": "Event",
      "sectionId": null,
      "formId": null,
      "id": null,
      "repeatableMin": null,
      "repeatableMax": null,
      "repeatable": false,
      "fields": [
        {
          "formId": null,
          "typeId": "11111111-1111-1111-1111-111111111111",
          "formSectionId": null,
          "id": null,
          "name": "title",
          "label": "Title",
          "labelEn": "Title",
          "description": null,
          "required": true,
          "order": 1,
          "computed": null
        },
        {
          "formId": null,
          "typeId": "22222222-2222-2222-2222-222222222222",
          "formSectionId": null,
          "id": null,
          "name": "occurredAt",
          "label": "Occurred At",
          "labelEn": "Occurred At",
          "description": null,
          "required": false,
          "order": 2,
          "computed": null
        },
        {
          "formId": null,
          "typeId": "33333333-3333-3333-3333-333333333333",
          "formSectionId": null,
          "id": null,
          "name": "description",
          "label": "Description",
          "labelEn": "Description",
          "description": null,
          "required": false,
          "order": 3,
          "computed": null
        }
      ],
      "sections": []
    }
  ]
}

"""
    )

    return prompt


@mcp.resource(
    description="extract sdl of the graphql endpoint",
    uri="resource://graphql/sdl",
    mime_type="application/json", # Explicit MIME type
    tags={"metadata"}, # Categorization tags
)
async def get_graphql_sdl(ctx: fastmcp.Context):
    import graphql
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

@mcp.prompt(
    description="build system prompt for tool router "
)
async def get_router_prompt(ctx: fastmcp.Context):
    ROUTER_SYSTEM_PROMPT = ("""You are a Tool Router for an MCP server.
    Your task: (1) choose the best tool from TOOLS_JSON, (2) return a STRICT JSON action,
    (3) if an ERROR_FROM_TOOL is provided, correct only the necessary arguments and return a new tool_call.

    Inputs you receive:
    - TOOLS_JSON: JSON array of tools with {name, description, arg_schema}
    - USER_MESSAGE: user's request
    - LAST_TOOL_ATTEMPT: optional last tool_call JSON
    - ERROR_FROM_TOOL: optional last tool error {code, message}
    - RETRY_COUNT, MAX_RETRIES: integers

    Output (JSON only; no prose):
    Either:
    { "action":"tool_call", "tool_name":"<name>", "arguments": {..}, "idempotency_key":"<string>", "postconditions":{"expectations":"<short>","success_criteria":["..."]}}
    or
    { "action":"ask_clarifying_question", "question":"<one precise question>", "missing_fields":["..."] }
    or
    { "action":"final_answer", "content":"<short answer>" }

    Rules:
    - Select the tool whose arg_schema and description fit USER_MESSAGE with minimal assumptions.
    - Validate argument types and formats against arg_schema (strings, numbers, booleans, date 'YYYY-MM-DD').
    - Use safe defaults only if present in arg_schema defaults; otherwise ask a clarifying question.
    - If ERROR_FROM_TOOL exists and RETRY_COUNT < MAX_RETRIES, fix only relevant arguments and return a new tool_call.
    - Never include any text except the JSON object.
    """    )
    return ROUTER_SYSTEM_PROMPT

@mcp.resource(
    description="returns the schema of response to router tool",
    uri="resource://mcp/router"
)
async def get_router_schema():
    
    ROUTER_OUTPUT_SCHEMA = {
        "type": "object",
        "oneOf": [
            {
                "properties": {
                    "action": {"const": "tool_call"},
                    "tool_name": {"type": "string"},
                    "arguments": {"type": "object"},
                    "idempotency_key": {"type": "string"},
                    "postconditions": {
                        "type": "object",
                        "properties": {
                            "expectations": {"type": "string"},
                            "success_criteria": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["expectations", "success_criteria"],
                        "additionalProperties": True,
                    },
                },
                "required": ["action", "tool_name", "arguments", "idempotency_key"],
                "additionalProperties": True,
            },
            {
                "properties": {
                    "action": {"const": "ask_clarifying_question"},
                    "question": {"type": "string"},
                    "missing_fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action", "question"],
                "additionalProperties": False,
            },
            {
                "properties": {
                    "action": {"const": "final_answer"},
                    "content": {"type": "string"},
                },
                "required": ["action", "content"],
                "additionalProperties": False,
            },
        ],
    }
    return ROUTER_OUTPUT_SCHEMA

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
     
@mcp.prompt(
    description=(
        "build system prompt for MCP tool router"
    )
)
async def tool_router():
    prompt = (
    """You are a Tool Router for an MCP server.
Your task: (1) choose the best tool from TOOLS_JSON, (2) return a STRICT JSON action,
(3) if an ERROR_FROM_TOOL is provided, correct only the necessary arguments and return a new tool_call.

Inputs you receive:
- TOOLS_JSON: JSON array of tools with {name, description, arg_schema}
- USER_MESSAGE: user's request
- LAST_TOOL_ATTEMPT: optional last tool_call JSON
- ERROR_FROM_TOOL: optional last tool error {code, message}
- RETRY_COUNT, MAX_RETRIES: integers

Output (JSON only; no prose):
Either:
{ "action":"tool_call", "tool_name":"<name>", "arguments": {..}, "idempotency_key":"<string>", "postconditions":{"expectations":"<short>","success_criteria":["..."]}}
or
{ "action":"ask_clarifying_question", "question":"<one precise question>", "missing_fields":["..."] }
or
{ "action":"final_answer", "content":"<short answer>" }

Rules:
- Select the tool whose arg_schema and description fit USER_MESSAGE with minimal assumptions.
- Validate argument types and formats against arg_schema (strings, numbers, booleans, date 'YYYY-MM-DD').
- Use safe defaults only if present in arg_schema defaults; otherwise ask a clarifying question.
- If ERROR_FROM_TOOL exists and RETRY_COUNT < MAX_RETRIES, fix only relevant arguments and return a new tool_call.
- Never include any text except the JSON object.
"""
    )
    return prompt


@mcp.prompt(
    description="acording user prompt the related graphql types are selected"
)
async def pickup_graphql_types(user_prompt: str, ctx: fastmcp.Context):
    typelist = await get_graphql_types.fn(ctx)
    prompt = f"""
# Instructions

You can pair objects mentioned by the user with GraphQL types described in the JSON below.
Analyze the user prompt and return only valid JSON: an array of strings, each exactly matching a type's `name`.
Respond with a single JSON array—no additional text, no code fences.

Rules:
1. Exclude any types whose names end with `"Error"`, unless explicitly requested.
2. Match on type name or on keywords found in the description.
3. Detect 1:N (one-to-many) or N:1 relationships between the matched types, and order the array so that each parent type appears immediately before its child types.


## Output Example

prompt:
    "Give me a list of study programs and their students"
output:
    ["ProgramGQLModel", "StudentGQLModel"]

## Types to select from

```json
    {json.dumps(typelist, indent=2)}
```
   
## User Prompt

```
{user_prompt}
```
"""
    return prompt


from jsonschema import validate as jsonschema_validate, Draft202012Validator, ValidationError
@mcp.tool(
    description=(
        "Tool router. "
        "Can decide which tool to choose. "
    ),
    tags={"toolrouter"}
)
async def tool_router(
    tools_json: typing.List[typing.Dict[str, typing.Any]],
    user_message: str,
    last_tool_attempt: typing.Optional[typing.Dict[str, typing.Any]] = None,
    error_from_tool: typing.Optional[typing.Dict[str, typing.Any]] = None,
    retry_count: int = 0,
    max_retries: int = 3,
    ctx: fastmcp.Context = None
) -> ToolResult:
    
    ROUTER_SYSTEM_PROMPT = await get_router_prompt.fn()
    messages = [
        json.dumps(
            {
                "TOOLS_JSON": tools_json,
                "USER_MESSAGE": user_message,
                "LAST_TOOL_ATTEMPT": last_tool_attempt,
                "ERROR_FROM_TOOL": error_from_tool,
                "RETRY_COUNT": retry_count,
                "MAX_RETRIES": max_retries,
            },
            ensure_ascii=False,
        ),
    ]

    llm_response = await ctx.sample(
        system_prompt=ROUTER_SYSTEM_PROMPT,
        messages=messages,
        temperature=0.2
    )

    try:
        data = json.loads(llm_response)
    except json.JSONDecodeError as e:
        return ToolResult(
            content=TextContent(
                type="text",
                text=f"LLM did not return valid JSON: {e}\n{llm_response}"
            ),
            structured_content={
                "sourceid": "8a238bdc-c97c-433e-bd2a-3f7760157a0f",
                "errors": [
                    f"LLM did not return valid JSON: {e}\n{llm_response}"
                ]
            }
        )
    

    ROUTER_OUTPUT_SCHEMA = await get_router_schema.fn()
    try:
        Draft202012Validator(ROUTER_OUTPUT_SCHEMA).validate(data)
    except ValidationError as e:
        # raise RuntimeError(f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}")
        return ToolResult(
            content=TextContent(
                type="text",
                text=f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}"
            ),
            structured_content={
                "sourceid": "7037075e-2f2a-4696-b693-bed0a2885630",
                "errors": [
                    f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}"
                ]
            }
        )
    return ToolResult(
        content=TextContent(
            type="text",
            text=f"{json.dumps(data)}"
        ),
        structured_content={
            "sourceid": "0459c509-61f3-4269-85ae-2c9283518cb6",
            "data": data
        }
    )



@mcp.tool(
    description=(
        "Asks graphql endpoint for data. "
        "If the query is known this is appropriate tool for extraction data from graphql endpoint. "
        "Data are returned as markdown table."
    ),
    tags={"graphql"}
)
async def ask_graphql_endpoint(
    # query: typing.Annotated[str, "graphql query"],
    # variables: typing.Annotated[dict, "variables for the graphql query"],
    query: str,
    variables: dict,
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
    llmresponse = await ctx.sample(
        messages=prompt
    )
    print(f"get_graphQL_data.llmresponse: {llmresponse}")
    type_list = json.loads(llmresponse.text)
    query = await build_graphql_query_nested.fn(
        types="/".join(type_list),
        ctx=ctx
    )
    
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
    response_data_set = await gqlClient(query=query)
    response_error = response_data_set.get("errors") 
    assert response_error is None, f"During query {query} got response {response_data_set}"
    response_data = response_data_set.get("data")
    assert response_data is not None, "Probably the graphql endpoint is not running"
    print(f"response_data: {response_data}")
    data_list = next(iter(response_data.values()), None)
    print(f"data_list: {data_list}")
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
                "variables": {},
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
    llmresponse = await ctx.sample(
        messages=[
            prompt,
            "\n\nUser message:\n\n"
            f"{user_message}"
        ]
    )
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


async def createGQLClient(*, url: str = "http://localhost:33001/api/gql", username: str, password: str, token: str = None):
    import aiohttp
    async def getToken():
        authurl = url.replace("/api/gql", "/oauth/login3")
        async with aiohttp.ClientSession() as session:
            # print(headers, cookies)
            async with session.get(authurl) as resp:
                json = await resp.json()

            payload = {
                **json,
                "username": username,
                "password": password
            }
            async with session.post(authurl, json=payload) as resp:
                json = await resp.json()
            # print(f"createGQLClient: {json}")
            token = json["token"]
        return token
    token = await getToken() if token is None else token
    total_attempts = 10
    async def client(query, variables={}, cookies={"authorization": token}):
        # gqlurl = "http://host.docker.internal:33001/api/gql"
        # gqlurl = "http://localhost:33001/api/gql"
        nonlocal total_attempts
        if total_attempts < 1:
            raise Exception(msg="Max attempts to reauthenticate to graphql endpoint has been reached")
        attempts = 2
        while attempts > 0:
            
            payload = {"query": query, "variables": variables}
            # print("Query payload", payload, flush=True)
            try:
                async with aiohttp.ClientSession() as session:
                    # print(headers, cookies)
                    async with session.post(url, json=payload, cookies=cookies) as resp:
                        # print(resp.status)
                        if resp.status != 200:
                            text = await resp.text()
                            # print(text, flush=True)
                            raise Exception(f"Unexpected GQL response", text)
                        else:
                            text = await resp.text()
                            # print(text, flush=True)
                            response = await resp.json()
                            # print(response, flush=True)
                            return response
            except aiohttp.ContentTypeError as e:
                attempts = attempts - 1
                total_attempts = total_attempts - 1
                print(f"attempts {attempts}-{total_attempts}", flush=True)
                nonlocal token
                token = await getToken()

    return client

# Připoj MCP router k umbrella app
# app.include_router(mcp, prefix="/mcp")
mcp_app = mcp.http_app(path="/")

# v následujícím dotazu identifikuj datové entity, a podmínky, které mají splňovat. seznam datových entit (jejich odhadnuté názvy) uveď jako json list obsahující stringy - názvy seznam podmínek uveď jako json list obsahující dict např. {"name": {"_eq": "Pavel"}} pokud se jedná o podmínku v relaci, odpovídající dict je tento {"related_entity": {"attribute_name": {"_eq": "value"}}} v dict nikdy není použit klíč, který by sdružoval více názvů atributů dotaz: najdi mi všechny uživatele, kteří jsou členy katedry K209
