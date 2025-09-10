import json
import dataclasses

import fastmcp

from ..mcpserver import mcp

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



# @mcp.prompt(
#     description="build system prompt for tool router "
# )
# async def get_router_prompt(ctx: fastmcp.Context):
#     ROUTER_SYSTEM_PROMPT = ("""You are a Tool Router for an MCP server.
#     Your task: (1) choose the best tool from TOOLS_JSON, (2) return a STRICT JSON action,
#     (3) if an ERROR_FROM_TOOL is provided, correct only the necessary arguments and return a new tool_call.

#     Inputs you receive:
#     - TOOLS_JSON: JSON array of tools with {name, description, arg_schema}
#     - USER_MESSAGE: user's request
#     - LAST_TOOL_ATTEMPT: optional last tool_call JSON
#     - ERROR_FROM_TOOL: optional last tool error {code, message}
#     - RETRY_COUNT, MAX_RETRIES: integers

#     Output (JSON only; no prose):
#     Either:
#     { "action":"tool_call", "tool_name":"<name>", "arguments": {..}, "idempotency_key":"<string>", "postconditions":{"expectations":"<short>","success_criteria":["..."]}}
#     or
#     { "action":"ask_clarifying_question", "question":"<one precise question>", "missing_fields":["..."] }
#     or
#     { "action":"final_answer", "content":"<short answer>" }

#     Rules:
#     - Select the tool whose arg_schema and description fit USER_MESSAGE with minimal assumptions.
#     - Validate argument types and formats against arg_schema (strings, numbers, booleans, date 'YYYY-MM-DD').
#     - Use safe defaults only if present in arg_schema defaults; otherwise ask a clarifying question.
#     - If ERROR_FROM_TOOL exists and RETRY_COUNT < MAX_RETRIES, fix only relevant arguments and return a new tool_call.
#     - Never include any text except the JSON object.
#     """    )
#     return ROUTER_SYSTEM_PROMPT


@mcp.prompt(
    description="acording user prompt the related graphql types are selected"
)
async def pickup_graphql_types(user_prompt: str, ctx: fastmcp.Context):
    from ..resources import get_graphql_types
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



@dataclasses.dataclass
class LinkItem:
    id: str
    label: str
    href: str
    category: str
    description: str = ""


CATALOG: list[LinkItem] = [
    # Studium a výuka
    LinkItem("Akreditace", "Akreditace", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Akreditace", "Studium a výuka",
             "Podpora akreditací a reakreditací, plánování výuky, info o předmětech."),
    LinkItem("Akreditace2017", "Akreditace pro NAÚ", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Akreditace2017", "Studium a výuka",
             "Akreditace programů dle NAÚ."),
    LinkItem("Guarantee", "Garance a Databáze kvalifikačních prací", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Guarantee", "Studium a výuka",
             "Kontrola a archiv závěrečných prací."),
    LinkItem("Harmonogram", "Harmonogram studia", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Harmonogram", "Studium a výuka",
             "Vytvoření a zobrazení harmonogramu studia a akcí."),
    LinkItem("InformaceOStudentechAStudiu", "Informace o studentech a studiu", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=InformaceOStudentechAStudiu", "Studium a výuka",
             "Správa a zpřístupnění informací o studentech a studiu."),
    LinkItem("Matrika", "Matrika studentů", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Matrika", "Studium a výuka",
             "Matrika studentů."),
    LinkItem("ProgramCZV", "Programy a kurzy CŽV", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=ProgramCZV", "Studium a výuka",
             "Studijní programy a kurzy celoživotního vzdělávání."),
    LinkItem("PrijimaciRizeniV3", "Přijímací řízení v3.0", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=PrijimaciRizeniV3", "Studium a výuka",
             "Přijímací řízení (stará i nová akreditace)."),
    LinkItem("PlanovaniVyuky", "Rozvrhy hodin v2.0 - nové", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=PlanovaniVyuky", "Studium a výuka",
             "Aplikace pro plánování výuky, rozvrhy."),
    LinkItem("Stanag", "Stanag", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Stanag", "Studium a výuka",
             "Jazyková zkouška STANAG."),
    LinkItem("StatniZkouska", "Státní zkoušky a obhajoby", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=StatniZkouska", "Studium a výuka",
             "Admin, přihlašování, komise, plán SZK/obhajob."),
    LinkItem("Stipendium", "Stipendium", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Stipendium", "Studium a výuka",
             "Stipendium za vynikající výsledky."),
    LinkItem("StudentskeHodnoceni", "Studentské hodnocení kvality výuky předmětu", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=StudentskeHodnoceni", "Studium a výuka",
             "Hodnocení kvality výuky."),
    LinkItem("VolitelnePredmety", "Volba volitelných předmětů", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=VolitelnePredmety", "Studium a výuka",
             "Výběr volitelných předmětů, nahrávání do plánů."),
    LinkItem("ZapisKeZkousce", "Zápis ke zkoušce a hodnocení studijních výsledků", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=ZapisKeZkousce", "Studium a výuka",
             "Přihlašování ke zkouškám, známky."),
    # Výzkum a vývoj
    LinkItem("Dymado", "Dymado", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Dymado", "Výzkum a vývoj", "Dymado."),
    LinkItem("VyzkumVyvojInovace", "Portál výzkumu, vývoje a inovací", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=VyzkumVyvojInovace", "Výzkum a vývoj",
             "Portál VaVaI."),
    # Logistika, personální, organizační
    LinkItem("ISHAP", "IS HAP", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=ISHAP", "Logistika/personální/organizační",
             "Hodnocení akademických pracovníků."),
    LinkItem("NepritomnostOsob", "Nepřítomnost osob", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=NepritomnostOsob", "Logistika/personální/organizační",
             "Zadání nepřítomnosti."),
    LinkItem("Konference", "Přihlašování na akce a soutěže", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Konference", "Logistika/personální/organizační",
             "Registrace na konference a soutěže."),
    LinkItem("Stravovani", "Stravování", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Stravovani", "Logistika/personální/organizační",
             "Objednání stravy."),
    # Podpora práce uživatelů s IS
    LinkItem("DispecinkServisPoz", "Dispečink", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=DispecinkServisPoz", "Podpora IS",
             "Servisní požadavky."),
    LinkItem("ElektronickaPosta", "Elektronická pošta", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=ElektronickaPosta", "Podpora IS",
             "E-mail UO."),
    LinkItem("FormularProVstupDoObjektu", "Formulář pro vstup", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=FormularProVstupDoObjektu", "Podpora IS",
             "Žádosti o vstup do objektu."),
    LinkItem("HlaseniKBU", "Hlášení podezření na KBU", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=HlaseniKBU", "Podpora IS",
             "Hlášení KBU."),
    LinkItem("MojeAP", "Moje AP - testovací verze", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=MojeAP", "Podpora IS",
             "Moje AP."),
    LinkItem("OperativniEvidence", "Operativní evidence počítačů", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=OperativniEvidence", "Podpora IS",
             "Správa a evidence počítačů."),
    LinkItem("SpravaStudentskeSite", "Počítačová síť na ubytovnách", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=SpravaStudentskeSite", "Podpora IS",
             "Správa studentské sítě."),
    LinkItem("PortalOsoba", "Portál osoby", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=PortalOsoba", "Podpora IS",
             "Osobní rozhraní."),
    LinkItem("UzivatelNastaveni", "Uživatelská nastavení a žádosti", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=UzivatelNastaveni", "Podpora IS",
             "Nastavení uživatele, žádosti."),
    LinkItem("VyjadreniSouhlasu", "Vyjádření souhlasu", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=VyjadreniSouhlasu", "Podpora IS",
             "Souhlas se zobrazením osobních údajů."),
    # E-learning
    LinkItem("APV", "APV Věcné plánování", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=APV", "E-learning",
             "Plánování věcné přípravy."),
    LinkItem("Moodle", "Moodle", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=Moodle", "E-learning",
             "E-learning UO."),
    LinkItem("TermSlovnik", "Vojenský terminologický slovník", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=TermSlovnik", "E-learning",
             "Jednoduchý terminologický slovník."),
    # Správa aplikací
    LinkItem("SpravaPC", "Přidělování počítačů do správy místním správcům KIS", "/PortalOsoba/Aplikace/AplikaceOdkaz?appName=SpravaPC", "Správa aplikací/administrace",
             "Přidělování PC místním správcům KIS."),
]

@mcp.prompt(
    name="link_prompt", 
    description="Prompt from application catalog."
)
async def link_prompt(query: str, top_k: int = 3):
    from fastmcp.prompts.prompt import Message
    SYSTEM = (
        "You select the best link for a user's query from a fixed CATALOG.\n"
        "Return ONLY JSON with keys: {\"final\": {id,label,category,href,reason}, \"candidates\": [ ... ]}.\n"
        "Pick strictly from the provided items by 'id'. Prefer exact task match; otherwise the most helpful.\n"
        "Language: Czech if the query is Czech."
    )
    _catalog_json = [dict(id=x.id, label=x.label, href=x.href, category=x.category, description=x.description) for x in CATALOG]
    messages =  [
        Message(SYSTEM, role="assistant"),
        Message(json.dumps({"catalog": _catalog_json, "user_query": query, "top_k": top_k}, ensure_ascii=False), role="assistant")
    ]
    result = [
        model.model_dump() for model in messages
    ]
    return result

