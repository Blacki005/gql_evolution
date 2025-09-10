import json

import fastmcp
from fastmcp import FastMCP
from fastmcp.tools.tool import TextContent
from mcp import SamplingMessage, IncludeContext, CreateMessageResult
from mcp.types import CreateMessageRequestParams

# from fastmcp.experimental.sampling.handlers.openai import OpenAISamplingHandler

from typing import Any, Iterable
from mcp.types import SamplingMessage, TextContent

import json

# Pomocná normalizace FastMCP zpráv na OpenAI Chat API formát
def _to_openai_messages(
    messages: str | list[str | SamplingMessage],
    system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        print(f"_to_openai_messages.convert to list")
        messages = [messages]

    out: list[dict[str, Any]] = []
    if system_prompt:
        print(f"_to_openai_messages.system_prompt append {system_prompt}")
        out.append({"role": "system", "content": system_prompt})

    for m in messages:
        # 1) holý string → user
        if isinstance(m, str):
            out.append({"role": "user", "content": m})
            print(f"_to_openai_messages.str_message {m}")

            continue
        print(f"_to_openai_messages.message {type(m)}")

        if isinstance(m, SamplingMessage):
            m = m.model_dump()
    
        print(f"_to_openai_messages.message {type(m)}")
        # 2) dict-like SamplingMessage
        role = m.get("role", "user")
        content = m.get("content")

        # 2a) už je to string
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        # 2b) jediný objekt (např. {"type":"text","text":"..."})
        if isinstance(content, dict):
            t = content.get("type")
            if t in ("text", "input_text", "output_text"):
                out.append({"role": role, "content": content.get("text", "")})
            else:
                # jiný typ partu – serializuj do textu
                out.append({"role": role, "content": json.dumps(content, ensure_ascii=False)})
            continue

        # 2c) seznam partů → zplošť na texty
        if isinstance(content, list):
            texts: list[str] = []
            for p in content:
                if isinstance(p, dict) and p.get("type") in ("text", "input_text", "output_text"):
                    txt = p.get("text") or p.get("content") or ""
                    if txt:
                        texts.append(txt)
                else:
                    texts.append(json.dumps(p, ensure_ascii=False))
            out.append({"role": role, "content": "\n".join(texts)})
            continue

        # fallback
        out.append({"role": role, "content": ""})

    return out


async def fallback_sample(
    messages: str | list[str | SamplingMessage],
    params: CreateMessageRequestParams,
    ctx,  # fastmcp.Context
):
    # vytáhni bezpečně parametry (některé nemusí být nastavené)
    system_prompt = getattr(params, "system_prompt", None)
    temperature = getattr(params, "temperature", None)
    max_tokens = getattr(params, "max_tokens", None)
    top_p = getattr(params, "top_p", None)
    stop = getattr(params, "stop", None)
    response_format = getattr(params, "response_format", None)
    # cokoliv dalšího si můžeš vytáhnout podobně (presence_penalty, frequency_penalty…)

    # Normalizace zpráv do OpenAI Chat formátu
    oai_messages = _to_openai_messages(messages, system_prompt=system_prompt)

    # Volitelně: lehký log do UI
    try:
        await ctx.info(f"Fallback sampling via chat.completions ({len(oai_messages)} msgs)")
    except Exception:
        pass

    # Sestav tělo požadavku — přidej jen nenull hodnoty
    body: dict[str, Any] = {"messages": oai_messages}
    if temperature is not None: body["temperature"] = temperature
    if max_tokens is not None:  body["max_tokens"] = max_tokens
    if top_p is not None:       body["top_p"] = top_p
    if stop:                    body["stop"] = stop
    if response_format:         body["response_format"] = response_format  # např. {"type":"json_object"}

    # POZOR na překlep: "gpt-5-nano" (ne "gtp")
    resp = await azureCompletions.create(
        model="gpt-5-nano",
        **body,
    )

    if not resp.choices:
        raise ValueError("No response from chat.completions")

    msg = resp.choices[0].message
    content = getattr(msg, "content", None) or ""
    # Pokud by model vrátil tool_calls (u fallbacku je typicky ignorujeme),
    # můžeš zde přidat jednoduchou serializaci, ale většinou chceme čistý text.

    return CreateMessageResult(
        content=TextContent(type="text", text=content),
        role="assistant",
        model=getattr(resp, "model", None),
    )


# MCP server instance
mcp = FastMCP(
    "My MCP Server",
    sampling_handler=fallback_sample,
    # sampling_handler_behavior="fallback"
)

from main_ai import azureCompletions


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

