import typing
import json
import dataclasses

# region mcp
import fastmcp
from fastmcp.tools.tool import ToolResult, TextContent

from .mcpserver import mcp
from main_ai import azureCompletions

import main_mcp.prompts
import main_mcp.resources
import main_mcp.tools

# from fastmcp.resources import ResourceRegistry
# async def fallback_sample(
#         messages: str | list[str | SamplingMessage],
#         system_prompt: str | None = None,
#         include_context: IncludeContext | None = None,
#         temperature: float | None = None,
#         max_tokens: int | None = None,
#         model_preferences = None,
#     ):
#     resp = await azureCompletions.create(
#             model="gtp-5-nano",          # = deployment name
#             messages=messages,
#             temperature=temperature,
#             max_tokens=max_tokens,
#         )
#     result = TextContent(
#         type="text",
#         text=resp.choices[0].message.content
#     )
#     return result

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

# @mcp.resource(
#     description="returns the schema of response to router tool",
#     uri="resource://mcp/router"
# )
# async def get_router_schema():
    
#     ROUTER_OUTPUT_SCHEMA = {
#         "type": "object",
#         "oneOf": [
#             {
#                 "properties": {
#                     "action": {"const": "tool_call"},
#                     "tool_name": {"type": "string"},
#                     "arguments": {"type": "object"},
#                     "idempotency_key": {"type": "string"},
#                     "postconditions": {
#                         "type": "object",
#                         "properties": {
#                             "expectations": {"type": "string"},
#                             "success_criteria": {"type": "array", "items": {"type": "string"}},
#                         },
#                         "required": ["expectations", "success_criteria"],
#                         "additionalProperties": True,
#                     },
#                 },
#                 "required": ["action", "tool_name", "arguments", "idempotency_key"],
#                 "additionalProperties": True,
#             },
#             {
#                 "properties": {
#                     "action": {"const": "ask_clarifying_question"},
#                     "question": {"type": "string"},
#                     "missing_fields": {"type": "array", "items": {"type": "string"}},
#                 },
#                 "required": ["action", "question"],
#                 "additionalProperties": False,
#             },
#             {
#                 "properties": {
#                     "action": {"const": "final_answer"},
#                     "content": {"type": "string"},
#                 },
#                 "required": ["action", "content"],
#                 "additionalProperties": False,
#             },
#         ],
#     }
#     return ROUTER_OUTPUT_SCHEMA
     
# @mcp.prompt(
#     description=(
#         "build system prompt for MCP tool router"
#     )
# )
# async def tool_router():
#     prompt = (
#     """You are a Tool Router for an MCP server.
# Your task: (1) choose the best tool from TOOLS_JSON, (2) return a STRICT JSON action,
# (3) if an ERROR_FROM_TOOL is provided, correct only the necessary arguments and return a new tool_call.

# Inputs you receive:
# - TOOLS_JSON: JSON array of tools with {name, description, arg_schema}
# - USER_MESSAGE: user's request
# - LAST_TOOL_ATTEMPT: optional last tool_call JSON
# - ERROR_FROM_TOOL: optional last tool error {code, message}
# - RETRY_COUNT, MAX_RETRIES: integers

# Output (JSON only; no prose):
# Either:
# { "action":"tool_call", "tool_name":"<name>", "arguments": {..}, "idempotency_key":"<string>", "postconditions":{"expectations":"<short>","success_criteria":["..."]}}
# or
# { "action":"ask_clarifying_question", "question":"<one precise question>", "missing_fields":["..."] }
# or
# { "action":"final_answer", "content":"<short answer>" }

# Rules:
# - Select the tool whose arg_schema and description fit USER_MESSAGE with minimal assumptions.
# - Validate argument types and formats against arg_schema (strings, numbers, booleans, date 'YYYY-MM-DD').
# - Use safe defaults only if present in arg_schema defaults; otherwise ask a clarifying question.
# - If ERROR_FROM_TOOL exists and RETRY_COUNT < MAX_RETRIES, fix only relevant arguments and return a new tool_call.
# - Never include any text except the JSON object.
# """
#     )
#     return prompt

# from jsonschema import validate as jsonschema_validate, Draft202012Validator, ValidationError
# @mcp.tool(
#     description=(
#         "Tool router. "
#         "Can decide which tool to choose. "
#     ),
#     tags={"toolrouter"}
# )
# async def tool_router(
#     tools_json: typing.List[typing.Dict[str, typing.Any]],
#     user_message: str,
#     last_tool_attempt: typing.Optional[typing.Dict[str, typing.Any]] = None,
#     error_from_tool: typing.Optional[typing.Dict[str, typing.Any]] = None,
#     retry_count: int = 0,
#     max_retries: int = 3,
#     ctx: fastmcp.Context = None
# ) -> ToolResult:
    
#     ROUTER_SYSTEM_PROMPT = await get_router_prompt.fn()
#     messages = [
#         json.dumps(
#             {
#                 "TOOLS_JSON": tools_json,
#                 "USER_MESSAGE": user_message,
#                 "LAST_TOOL_ATTEMPT": last_tool_attempt,
#                 "ERROR_FROM_TOOL": error_from_tool,
#                 "RETRY_COUNT": retry_count,
#                 "MAX_RETRIES": max_retries,
#             },
#             ensure_ascii=False,
#         ),
#     ]

#     llm_response = await ctx.sample(
#         system_prompt=ROUTER_SYSTEM_PROMPT,
#         messages=messages,
#         temperature=0.2
#     )

#     try:
#         data = json.loads(llm_response)
#     except json.JSONDecodeError as e:
#         return ToolResult(
#             content=TextContent(
#                 type="text",
#                 text=f"LLM did not return valid JSON: {e}\n{llm_response}"
#             ),
#             structured_content={
#                 "sourceid": "8a238bdc-c97c-433e-bd2a-3f7760157a0f",
#                 "errors": [
#                     f"LLM did not return valid JSON: {e}\n{llm_response}"
#                 ]
#             }
#         )
    

#     ROUTER_OUTPUT_SCHEMA = await get_router_schema.fn()
#     try:
#         Draft202012Validator(ROUTER_OUTPUT_SCHEMA).validate(data)
#     except ValidationError as e:
#         # raise RuntimeError(f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}")
#         return ToolResult(
#             content=TextContent(
#                 type="text",
#                 text=f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}"
#             ),
#             structured_content={
#                 "sourceid": "7037075e-2f2a-4696-b693-bed0a2885630",
#                 "errors": [
#                     f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}"
#                 ]
#             }
#         )
#     return ToolResult(
#         content=TextContent(
#             type="text",
#             text=f"{json.dumps(data)}"
#         ),
#         structured_content={
#             "sourceid": "0459c509-61f3-4269-85ae-2c9283518cb6",
#             "data": data
#         }
#     )



# Připoj MCP router k umbrella app
# app.include_router(mcp, prefix="/mcp")
mcp_app = mcp.http_app(path="/")
mcp_app_sse = mcp.sse_app(path="/")
# mcp.sse_app()
# v následujícím dotazu identifikuj datové entity, a podmínky, které mají splňovat. seznam datových entit (jejich odhadnuté názvy) uveď jako json list obsahující stringy - názvy seznam podmínek uveď jako json list obsahující dict např. {"name": {"_eq": "Pavel"}} pokud se jedná o podmínku v relaci, odpovídající dict je tento {"related_entity": {"attribute_name": {"_eq": "value"}}} v dict nikdy není použit klíč, který by sdružoval více názvů atributů dotaz: najdi mi všechny uživatele, kteří jsou členy katedry K209

# C:\Users\admin\.dive\config

# {
#     "groups": [
#         {
#             "modelProvider": "openai_compatible",
#             "models": [
#                 {
#                     "disableStreaming": false,
#                     "active": true,
#                     "toolsInPrompt": false,
#                     "extra": {},
#                     "model": "gpt-5-nano",
#                     "isCustomModel": true,
#                     "verifyStatus": "ignore"
#                 },
#                 {
#                     "disableStreaming": false,
#                     "active": true,
#                     "toolsInPrompt": false,
#                     "extra": {
#                         "label": "GQL",
#                         "customInstructions": "You are graphql expert. For response to user prompt prefer usage of available tools. Do not invent queries or data."
#                     },
#                     "model": "gpt-5-nano-gql",
#                     "isCustomModel": true,
#                     "verifyStatus": "ignore"
#                 },
#                 {
#                     "disableStreaming": false,
#                     "active": false,
#                     "toolsInPrompt": false,
#                     "extra": {},
#                     "model": "gpt-azure",
#                     "isCustomModel": false,
#                     "verifyStatus": "unVerified"
#                 }
#             ],
#             "extra": {
#                 "active": true,
#                 "skip_tls_verify": true
#             },
#             "maxTokens": null,
#             "active": true,
#             "apiKey": "sk-cokoliv",
#             "baseURL": "http://localhost:8798"
#         }
#     ],
#     "common": {
#         "configuration": {
#             "temperature": 0,
#             "topP": 0
#         }
#     },
#     "disableDiveSystemPrompt": false
# }