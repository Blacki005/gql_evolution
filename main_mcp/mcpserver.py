import fastmcp
from fastmcp import FastMCP, Client
from fastmcp.tools.tool import ToolResult, TextContent
from mcp import SamplingMessage, IncludeContext, CreateMessageResult

from fastmcp.experimental.sampling.handlers.openai import OpenAISamplingHandler

async def fallback_sample(
    messages: str | list[str | SamplingMessage],
    system_prompt: str | None = None,
    include_context: IncludeContext | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model_preferences = None,
):
    if isinstance(messages, list):
        msg_norm = [
            {"role": "user", "content": msg} if isinstance(msg, str) else msg
            for msg in messages
        ]
    elif isinstance(messages, str):
        msg_norm = [
            {"role": "user", "content": messages}
        ]
    else:
        msg_norm = messages

    chat_completion = await azureCompletions.create(
        model="gpt-5-nano",          # = deployment name
        # model="summarization-deployment",
        # messages=messages if isinstance(messages, list) else [messages],
        messages=msg_norm,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    if len(chat_completion.choices) == 0:
        raise ValueError("No response for completion")

    first_choice = chat_completion.choices[0]
    content = first_choice.message.content
    # if content:
    #     return CreateMessageResult(
    #         content=TextContent(type="text", text=content),
    #         role="assistant",
    #         model=chat_completion.model,
    #     )
    
    return TextContent(
        type="text",
        text=content
    )
    raise Exception("fakt je to blbe")
    
     
    # return result


# MCP server instance
mcp = FastMCP(
    "My MCP Server",
    # sampling_handler=fallback_sample,
    # sampling_handler_behavior="fallback"
)

from main_ai import azureCompletions

