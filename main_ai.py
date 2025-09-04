import json
import typing
import dataclasses
import inspect
import datetime
import hashlib

from jsonschema import validate as jsonschema_validate, Draft202012Validator, ValidationError

from dotenv import load_dotenv
load_dotenv("environment.txt", override=False)
load_dotenv("environment.secret.txt", override=False)
load_dotenv("environment.super.secret.txt", override=False)

import os
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
account = os.getenv("AZURE_COGNITIVE_ACCOUNT_NAME", "")
model_name = os.getenv("AZURE_CHAT_DEPLOYMENT_NAME", "") or "summarization-deployment"
endpoint = f"https://{account}.openai.azure.com"

# from langchain_openai import AzureChatOpenAI
# from langchain.chat_models import AzureChatOpenAI #.azure_openai import AzureChatOpenAI
# from langchain_community import chat_models
# 2) LLM (Azure OpenAI)
# llm = AzureChatOpenAI(
#     azure_endpoint=endpoint,
#     deployment=model_name,  # tvůj deployment name
#     api_key=OPENAI_API_KEY,
#     api_version="2024-12-01-preview"
# )
import asyncio
from openai import AzureOpenAI, AsyncAzureOpenAI
from openai.types.chat import ChatCompletion
from openai.resources.chat.completions import AsyncCompletions

client = AsyncAzureOpenAI(
    azure_endpoint=endpoint,
    azure_deployment=model_name,  # tvůj deployment name
    api_key=OPENAI_API_KEY,
    api_version="2024-12-01-preview"
)

azureCompletions: AsyncCompletions = client.chat.completions

class ChatSession:
    def __init__(self, system_prompt: str = "You are a helpful assistant.",
                 max_turns: int = 12):
        # 1 turn = 1 user + 1 assistant zpráva
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.messages: typing.List[typing.Dict[str, typing.Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.azureCompletions: AsyncCompletions = client.chat.completions

    def _trim_history(self) -> None:
        # nechá první system zprávu + posledních N tahů
        # (tj. max 1 + 2*max_turns zpráv)
        # najdi index první user/assistant zprávy od konce:
        # jednoduché řešení – seřízni na posledních (2*max_turns) zpráv + system
        
        keep = 1 + 2 * self.max_turns
        if len(self.messages) > keep:
            self.messages = [self.messages[0]] + self.messages[-(keep - 1):]

    async def get_history(self) -> typing.List[typing.Dict[str, typing.Any]]:
        keep = 1 + 2 * self.max_turns
        result = [self.messages[0]] + self.messages[-(keep - 1):]
        return result

    async def append_history(self, message) -> typing.List[typing.Dict[str, typing.Any]]:
        self.messages.append(message)
        return self.messages

    async def ask(
        self, 
        user_text: str, 
        *, 
        temperature: float = 0.2,
        max_tokens: int = 800
    ) -> str:
        await self.append_history({"role": "user", "content": user_text})
        history: list = await self.get_history()
        # history.insert(0, self.system_prompt)
        resp = await self.azureCompletions.create(
            model=model_name,          # = deployment name
            messages=history,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        reply = resp.choices[0].message.content or ""
        usage = resp.usage.model_dump()
        await self.append_history({"role": "assistant", "content": reply, "usage": usage})
        return reply

class ToolError(Exception):
    def __init__(self, message: str, code: str = "TOOL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclasses.dataclass
class RouterContext:
    user_message: str
    tools_json: list[dict] = dataclasses.field(default_factory=list)

    # výsledek routování
    selected_tool: typing.Optional[str] = None
    arguments: dict | None = None

    # běh nástroje
    attempt: int = 0
    max_retries: int = 3
    result: typing.Any = None
    error: dict | None = None

    # volitelná metadata
    meta: dict = dataclasses.field(default_factory=dict)


class FilterType:
    ROUTE_SELECT   = "route_select"    # před výběrem nástroje (LLM routing apod.)
    ROUTE_ERROR    = "route_error"     # při chybě v průbehu identifikace nástroje
    TOOL_CALL      = "tool_call"       # těsně před voláním nástroje
    TOOL_RESULT    = "tool_result"     # po úspěšném volání nástroje
    TOOL_ERROR     = "tool_error"      # po chybě volání nástroje (pro self-repair)
    PROMPT_RENDER  = "prompt_render"   # pokud generuješ prompt pro routing (volitelné)

class MCPRouter:

    def __init__(self, mcpClient):
        self._filters: dict[str, list[typing.Callable]] = {}
        self.mcpClient = mcpClient

    def filter(self, *, filter_type: str):
        """Decorator: @router.filter(filter_type=FilterType.TOOL_CALL)"""
        def decorator(fn: typing.Callable):
            self._filters.setdefault(filter_type, []).append(fn)
            return fn  # vracíme původní funkci (registrace má side-effect)
        return decorator

    async def _run_pipeline(
        self,
        filter_type: str,
        context: RouterContext,
        final: typing.Callable[[RouterContext], typing.Awaitable[typing.Any]],
    ):
        """Spustí filtry daného typu; poslední je 'final'. Filtr dostane (context, next)."""
        filters = self._filters.get(filter_type, [])

        async def _invoke(i: int, ctx: RouterContext):
            if i < len(filters):
                fn = filters[i]

                async def _next(new_ctx: RouterContext | None = None):
                    return await _invoke(i + 1, new_ctx or ctx)

                # podpora sync i async filtrů
                res = fn(ctx, _next)
                if inspect.isawaitable(res):
                    return await res
                return res
            else:
                return await final(ctx)

        return await _invoke(0, context)

    def systemPrompt(self):
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
    
    def outputSchema(self):
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

    @staticmethod
    def _extract_json(text: str):
        """Vrátí dict z JSON odpovědi i když je obalená textem / ```json ...```."""
        if not isinstance(text, str):
            raise ValueError("LLM response is not a string")
        # 1) zkus rovnou JSON
        try:
            return json.loads(text)
        except Exception:
            pass
        # 2) code-fence ```json ... ```
        m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            return json.loads(m.group(1))
        # 3) first { ... last } heuristika
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
        raise ValueError("No JSON object found in LLM response")

    @staticmethod
    def _normalize_router_output(d: dict) -> dict:
        """Opraví časté překlepy: toolname→tool_name, atd.; normalizuje action aliasy."""
        if not isinstance(d, dict):
            return d
        mapping = {
            "toolname": "tool_name",
            "idempotencykey": "idempotency_key",
            "successcriteria": "success_criteria",
            "postcondition": "postconditions",
        }
        for k_old, k_new in list(mapping.items()):
            if k_old in d and k_new not in d:
                d[k_new] = d.pop(k_old)

        # normalizuj action aliasy → tool_call
        action = d.get("action")
        if isinstance(action, str):
            alias = action.lower().replace("-", "_")
            if alias in {
                "toolcall", "call_tool", "calltool", "invoke_tool",
                "getgraphqldata", "get_graphql_data", "getgraphQLdata".lower(), "get_graphQL_data".lower()
            }:
                d["action"] = "tool_call"

        # postconditions vnořená oprava
        pc = d.get("postconditions")
        if isinstance(pc, dict) and "successcriteria" in pc and "success_criteria" not in pc:
            pc["success_criteria"] = pc.pop("successcriteria")
        return d

    @staticmethod
    def _canonical_tool_name(name: str, tools_json: list[dict]) -> str | None:
        """Najde kanonické jméno nástroje v TOOLS_JSON (case/underscore insensitive)."""
        if not name:
            return None
        names = [t.get("name") for t in tools_json or [] if t.get("name")]
        if name in names:
            return name
        lower_map = {n.lower(): n for n in names}
        if name.lower() in lower_map:
            return lower_map[name.lower()]
        # underscore/space insensitivity
        def norm(s): return re.sub(r"[\s_]+", "", s).lower()
        norm_map = {norm(n): n for n in names}
        return norm_map.get(norm(name))

    async def planner(self, ctx: RouterContext) -> RouterContext:
        """
        LLM router → vybere nástroj a argumenty (s retry & sanitizací výstupu).
        """
        ROUTER_SYSTEM_PROMPT = self.systemPrompt()
        ROUTER_OUTPUT_SCHEMA = self.outputSchema()
        chat = ChatSession(system_prompt=ROUTER_SYSTEM_PROMPT)

        # Kolikrát zkusit opravit/plánovat (nezaměňuj s tool retry)
        router_retries = min(max(ctx.max_retries, 1), 3)  # např. 1–3 pokusy

        last_error = None
        last_raw = None

        for rtry in range(router_retries):
            system_prompt = ctx.meta.get("override_system_prompt", self.systemPrompt())
            chat = ChatSession(system_prompt=system_prompt)
            payload = {
                "TOOLS_JSON": ctx.tools_json,
                "USER_MESSAGE": ctx.user_message,
                "LAST_TOOL_ATTEMPT": ctx.meta.get("LAST_TOOL_ATTEMPT"),
                "ERROR_FROM_TOOL": ctx.error,     # při prvním průchodu None
                "RETRY_COUNT": rtry,
                "MAX_RETRIES": router_retries,
            }

            llm_response = await chat.ask(
                user_text=json.dumps(payload, ensure_ascii=False),
                temperature=0.2,
                max_tokens=1000,
            )
            last_raw = llm_response

            # 1) Parse & normalize
            try:
                data = self._extract_json(llm_response)
                data = self._normalize_router_output(data)
            except Exception as e:
                last_error = f"Router JSON parse failed: {e}"
                ctx.meta["router_last_error"] = last_error
                ctx.meta["router_last_raw"] = last_raw
                async def _noop(_): return None
                await self._run_pipeline(FilterType.ROUTE_ERROR, ctx, _noop)
                continue # dalsi pokus

            # 2) Validate
            try:
                Draft202012Validator(ROUTER_OUTPUT_SCHEMA).validate(data)
            except ValidationError as e:
                last_error = f"Router output schema validation failed: {e.message}"
                ctx.meta["router_last_error"] = last_error
                ctx.meta["router_last_raw"] = data
                async def _noop(_): return None
                await self._run_pipeline(FilterType.ROUTE_ERROR, ctx, _noop)
                continue

            # 3) Handle action
            action = data.get("action")

            if action == "tool_call":
                tool_name = data.get("tool_name")
                # kanonizace jména podle TOOLS_JSON
                canon = self._canonical_tool_name(tool_name, ctx.tools_json)
                if canon is None:
                    last_error = f"Unknown tool '{tool_name}' (not found in TOOLS_JSON)."
                    ctx.meta["router_last_error"] = last_error
                    ctx.meta["router_last_raw"] = data
                    async def _noop(_): return None
                    await self._run_pipeline(FilterType.ROUTE_ERROR, ctx, _noop)
                    continue

                ctx.selected_tool = canon
                ctx.arguments = data.get("arguments") or {}
                ctx.meta["idempotency_key"] = data.get("idempotency_key")
                ctx.meta["postconditions"] = data.get("postconditions")
                ctx.meta["router_raw"] = data
                return ctx

            if action == "ask_clarifying_question":
                ctx.meta["router_question"] = data["question"]
                ctx.meta["router_missing_fields"] = data.get("missing_fields", [])
                ctx.meta["router_raw"] = data
                return ctx  # bez selected_tool – necháme nadřazenou logiku rozhodnout

            if action == "final_answer":
                ctx.meta["router_final_answer"] = data["content"]
                ctx.meta["router_raw"] = data
                return ctx

            last_error = f"Unknown router action: {action}"

        # po vyčerpání pokusů
        detail = (last_raw[:400] + "...") if isinstance(last_raw, str) and len(last_raw) > 400 else last_raw
        raise RuntimeError(f"Router planning failed after {router_retries} attempts. Last error: {last_error}\nLast response: {detail}")
    
    async def invoker(self, ctx: RouterContext):
        if not ctx.selected_tool:
            raise RuntimeError("No tool selected in context.")
        args = (ctx.arguments or {}).copy()

        # 1) Najdi schema pro vybraný tool (pokud je k dispozici)
        tool_schema = None
        for t in (ctx.tools_json or []):
            if t.get("name") == ctx.selected_tool:
                tool_schema = t.get("arg_schema")
                break

        # 2) Aplikuj defaulty (shallow) a validuj JSON Schema
        if tool_schema:
            props = tool_schema.get("properties", {})
            for k, spec in props.items():
                if "default" in spec and k not in args:
                    args[k] = spec["default"]
            try:
                Draft202012Validator(tool_schema).validate(args)
            except ValidationError as e:
                raise ToolError(f"Argument validation failed: {e.message}", code="VALIDATION_ERROR")
        ctx.arguments = args  # ulož zpět do kontextu (po defaultech)

        # 3) Idempotency key (deterministicky dle toolu a kanonických argumentů)
        if not ctx.meta.get("idempotency_key"):
            canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            raw = f"{ctx.selected_tool}|{canonical}"
            ctx.meta["idempotency_key"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

        # 4) Volání MCP nástroje (s fallbackem, pokud signatura nepodporuje idempotency_key)
        mcpClient = self.mcpClient
        try:
            try:
                result = await mcpClient.call_tool(
                    ctx.selected_tool,
                    ctx.arguments,
                    idempotency_key=ctx.meta["idempotency_key"],
                )
            except TypeError:
                # starší/odlišná signatura
                result = await mcpClient.call_tool(ctx.selected_tool, ctx.arguments)
        except Exception as ex:
            # Zarovnej na jednotnou chybu pro retry logiku
            code = getattr(ex, "code", "RUNTIME_ERROR")
            raise ToolError(str(ex), code=code)

        # 5) Podpora streamu (pokud tool vrací async iterator)
        if hasattr(result, "__aiter__"):
            chunks = []
            async for chunk in result:
                chunks.append(chunk)
            return {"streamed": True, "chunks": chunks}

        return result
    
    async def route_and_call(
        self,
        context: RouterContext,
        *,
        planner: typing.Callable[[RouterContext], typing.Awaitable[RouterContext]] = None,
        invoker: typing.Callable[[RouterContext], typing.Awaitable[typing.Any]] = None,
    ) -> RouterContext:
        """
        planner: naplní context.selected_tool + context.arguments (LLM routing apod.)
        invoker: provede vlastní volání MCP nástroje dle context.selected_tool/arguments
        """

        if planner is None:
            planner = self.planner
        if invoker is None:
            invoker = self.invoker

        # 1) ROUTING (filtry kolem výběru nástroje)
        async def _final_route(ctx: RouterContext):
            # planner může vrátit nový/aktualizovaný kontext nebo jen mutovat stávající
            maybe_ctx = await planner(ctx)
            return maybe_ctx or ctx

        context = await self._run_pipeline(FilterType.ROUTE_SELECT, context, _final_route)
        if not context.selected_tool:
            return context
            # raise RuntimeError("Router did not select a tool.")

        # 2) VOLÁNÍ NÁSTROJE + RETRY (filtry před/po / na chybu)
        for attempt in range(context.max_retries + 1):
            context.attempt = attempt
            context.error = None
            context.result = None

            async def _final_call(ctx: RouterContext):
                # skutečné volání nástroje
                return await invoker(ctx)

            try:
                # filtry před voláním nástroje
                result = await self._run_pipeline(FilterType.TOOL_CALL, context, _final_call)
                context.result = result

                # filtry po úspěšném výsledku
                async def _final_result(ctx: RouterContext):
                    return ctx.result
                await self._run_pipeline(FilterType.TOOL_RESULT, context, _final_result)

                return context  # hotovo

            except Exception as ex:
                # ulož chybu do contextu
                context.error = {
                    "code": getattr(ex, "code", "RUNTIME_ERROR"),
                    "message": str(ex),
                    "type": ex.__class__.__name__,
                }

                # filtry pro chybu (mohou upravit arguments, selected_tool, meta…)
                async def _final_error(ctx: RouterContext):
                    # defaultní final pro error nic nevrací → pokračuj retry
                    return None
                await self._run_pipeline(FilterType.TOOL_ERROR, context, _final_error)

                if attempt >= context.max_retries:
                    raise  # po vyčerpání retry předej výš


# async def call_llm_router(
#     tools_json: typing.List[typing.Dict[str, typing.Any]],
#     user_message: str,
#     last_tool_attempt: typing.Optional[typing.Dict[str, typing.Any]] = None,
#     error_from_tool: typing.Optional[typing.Dict[str, typing.Any]] = None,
#     retry_count: int = 0,
#     max_retries: int = 3,
#     ROUTER_SYSTEM_PROMPT: str = None,
#     ROUTER_OUTPUT_SCHEMA: str = None
# ) -> typing.Dict[str, typing.Any]:
    
#     chat = ChatSession(system_prompt=ROUTER_SYSTEM_PROMPT)
#     chat.append_history(
#         {
#             "role": "user",
#             "content": json.dumps(
#                 {
#                     "TOOLS_JSON": tools_json,
#                     "USER_MESSAGE": user_message,
#                     "LAST_TOOL_ATTEMPT": last_tool_attempt,
#                     "ERROR_FROM_TOOL": error_from_tool,
#                     "RETRY_COUNT": retry_count,
#                     "MAX_RETRIES": max_retries,
#                 },
#                 ensure_ascii=False,
#             ),
#         }
#     )
    
#     # resp = client.chat.completions.create(
#     #     model=LLM_MODEL,
#     #     messages=messages,
#     #     temperature=0.2,
#     #     response_format={"type": "json_object"},
#     # )
#     # text = resp.choices[0].message.content
    
#     llm_response = await chat.ask(
#         user_text="",
#         temperature=0.2
#     )
#     try:
#         data = json.loads(llm_response)
#     except json.JSONDecodeError as e:
#         raise RuntimeError(f"LLM did not return valid JSON: {e}\n{llm_response}")
#     # Validace základního tvaru router výstupu
#     try:
#         Draft202012Validator(ROUTER_OUTPUT_SCHEMA).validate(data)
#     except ValidationError as e:
#         raise RuntimeError(f"Router output schema validation failed: {e.message}\nGot: {json.dumps(data, ensure_ascii=False)}")
#     return data

# def idempotency_key(tool_name: str, arguments: typing.Dict[str, typing.Any]) -> str:
#     h = hashlib.sha256()
#     h.update(tool_name.encode("utf-8"))
#     h.update(json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode("utf-8"))
#     return h.hexdigest()[:32]

# def today_iso_date_tz(tz: datetime.timezone = datetime.timezone.utc) -> str:
#     return datetime.datetime.now(tz).date().isoformat()

# async def route_and_call_tool(
#     user_message: str, 
#     tools: list[dict], 
#     max_retries: int = 3,
#     mcpClient = None
# ) -> typing.Dict[str, typing.Any]:
    
#     def get_tool_by_name(name: str) -> typing.Dict[str, typing.Any]:
#         for t in tools:
#             if t["name"] == name:
#                 return t
#         raise KeyError(f"Unknown tool '{name}'")

#     def validate_tool_arguments(
#         tool: typing.Dict[str, typing.Any], 
#         arguments: typing.Dict[str, typing.Any]
#     ) -> None:
#         schema = tool["arg_schema"]
#         Draft202012Validator(schema).validate(arguments)

#     last_attempt = None
#     error_from_tool = None

#     ROUTER_SYSTEM_PROMPT = await mcpClient.get_prompt(
#         name="get_router_prompt",
#         arguments={}
#     )

#     ROUTER_OUTPUT_SCHEMA = await mcpClient.get_resource(
#         name="get_router_schema",
#         arguments={}
#     )
    
#     for attempt in range(0, max_retries + 1):
#         router_out = await call_llm_router(
#             tools_json=tools,
#             user_message=user_message,
#             last_tool_attempt=last_attempt,
#             error_from_tool=error_from_tool,
#             retry_count=attempt if error_from_tool else 0,
#             max_retries=max_retries,
#             ROUTER_SYSTEM_PROMPT = ROUTER_SYSTEM_PROMPT,
#             ROUTER_OUTPUT_SCHEMA = ROUTER_OUTPUT_SCHEMA
#         )

#         action = router_out.get("action")

#         if action == "final_answer":
#             return {"status": "ok", "type": "final_answer", "data": router_out["content"]}

#         if action == "ask_clarifying_question":
#             # V produkci: předej dotaz uživateli a počkej na odpověď.
#             # Zde jen vrátíme dotaz volajícímu.
#             return {"status": "needs_user_input", "question": router_out["question"], "missing_fields": router_out.get("missing_fields", [])}

#         if action == "tool_call":
#             tool_name = router_out["tool_name"]
#             arguments = router_out["arguments"]
#             # doplň idempotency_key pokud chybí (LLM ho má generovat, ale pojistka)
#             router_out.setdefault("idempotency_key", idempotency_key(tool_name, arguments))

#             try:
#                 tool = get_tool_by_name(tool_name)
#             except KeyError as e:
#                 # Neznámý nástroj → pošli chybu zpět LLM k opravě
#                 last_attempt = router_out
#                 error_from_tool = {"code": "UNKNOWN_TOOL", "message": str(e)}
#                 continue

#             # Validace argumentů proti schématu (před samotným voláním)
#             try:
#                 validate_tool_arguments(tool, arguments)
#             except ValidationError as e:
#                 last_attempt = router_out
#                 error_from_tool = {"code": "VALIDATION_ERROR", "message": e.message}
#                 continue

#             # Vykonání nástroje

#             # impl = TOOL_IMPL.get(tool_name)
#             # if not impl:
#             #     last_attempt = router_out
#             #     error_from_tool = {"code": "NOT_IMPLEMENTED", "message": f"No impl for {tool_name}"}
#             #     continue
            
#             try:

#                 # result = impl(arguments)
#                 result = await mcpClient.call_tool(
#                     name=tool_name,
#                     arguments=arguments
#                 )
                
#                 return {
#                     "status": "ok",
#                     "type": "tool_result",
#                     "tool": tool_name,
#                     "arguments": arguments,
#                     "result": result,
#                     "idempotency_key": router_out["idempotency_key"],
#                 }
#             except ToolError as te:
#                 # Chyba nástroje → vrátíme LLM a požádáme o opravu parametrů
#                 last_attempt = router_out
#                 error_from_tool = {"code": te.code, "message": te.message}
#                 continue
#             except Exception as ex:
#                 last_attempt = router_out
#                 error_from_tool = {"code": "RUNTIME_ERROR", "message": str(ex)}
#                 continue

#     # Vyčerpali jsme retry pokusy
#     return {"status": "error", "message": f"Unable to obtain a successful tool call after {max_retries} retries.", "last_error": error_from_tool}


async def main():
    session = ChatSession(system_prompt="You are a helpful assistant that answers in Czech.")
    # print(await session.ask("Napiš mi vtip o kočkách."))
    # print(await session.ask("A teď ho zopakuj."))

# asyncio.run(main())
asyncio.get_running_loop().create_task(main())
# print(dir(llm))