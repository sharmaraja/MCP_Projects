import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).resolve().with_name("mcp_server.py"))],
    env=os.environ.copy(),
    cwd=str(PROJECT_ROOT),
)

async def get_mcp_capabilities() -> dict:
    """Connect to the MCP server and discover all Tools, Resources, and Prompts."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_res = await session.list_tools()
            resources_res = await session.list_resources()
            templates_res = await session.list_resource_templates()
            prompts_res = await session.list_prompts()

            return {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "read_only": getattr(t.annotations, "read_only_hint", None) if t.annotations else None,
                        "schema": t.input_schema,
                    }
                    for t in tools_res.tools
                ],
                "resources": [
                    {"uri": str(r.uri), "name": r.name, "description": r.description}
                    for r in resources_res.resources
                ],
                "resource_templates": [
                    {"uriTemplate": t.uri_template, "name": t.name, "description": t.description}
                    for t in templates_res.resource_templates
                ],
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "arguments": [a.name for a in (p.arguments or [])],
                    }
                    for p in prompts_res.prompts
                ],
            }

async def read_resource_content(uri: str) -> str:
    """Read an MCP Resource (static or dynamic URI) directly from the server."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource(uri)
            return "\n".join(
                block.text for block in result.contents if hasattr(block, "text")
            )

async def render_mcp_prompt(prompt_name: str, arguments: dict) -> str:
    """Fetch a rendered prompt workflow template from the MCP server."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.get_prompt(prompt_name, arguments=arguments)
            return "\n".join(
                msg.content.text for msg in result.messages if hasattr(msg.content, "text")
            )

async def run_mcp_agent_turn(chat_history: list[dict], user_message: str) -> tuple[str, list[dict]]:
    """
    Runs an agentic LLM turn:
    1. Injects the `finance://schema` MCP Resource into system context.
    2. Discovers MCP Tools dynamically and converts them to Groq tool schemas.
    3. Executes any model-requested MCP tool calls over the active MCP session.
    """
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    tool_traces = []

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Load schema resource automatically as grounding context
            schema_res = await session.read_resource("finance://schema")
            schema_text = "\n".join(
                b.text for b in schema_res.contents if hasattr(b, "text")
            )

            # 2. Convert MCP Tools to OpenAI/Groq function-calling format
            mcp_tools = (await session.list_tools()).tools
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.input_schema,
                    },
                }
                for t in mcp_tools
            ]

            system_prompt = (
                "You are an expert Personal Finance & UPI Analytics Assistant connected to an MCP Server.\n"
                "Use the provided MCP tools to query exact figures in INR (₹) rather than guessing.\n\n"
                f"Database Context (from MCP Resource `finance://schema`):\n{schema_text}"
            )

            messages = [{"role": "system", "content": system_prompt}]
            for msg in chat_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_message})

            # 3. Tool-calling execution loop
            for _ in range(5):
                response = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=messages,
                    tools=groq_tools,
                    tool_choice="auto",
                    temperature=0.0,
                )

                assistant_msg = response.choices[0].message
                if not assistant_msg.tool_calls:
                    return assistant_msg.content or "Done.", tool_traces

                messages.append(assistant_msg.model_dump(exclude_none=True))

                for tc in assistant_msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments or "{}")

                    # Invoke tool over MCP protocol
                    mcp_result = await session.call_tool(tool_name, arguments=tool_args)
                    output_text = "\n".join(
                        b.text for b in mcp_result.content if hasattr(b, "text")
                    )

                    tool_traces.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "output": output_text,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": output_text,
                    })

            return "Reached maximum tool execution steps.", tool_traces