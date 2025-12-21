import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ORDER_MCP_URL = os.getenv("ORDER_MCP_URL", "http://127.0.0.1:8002/mcp")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

async def call_order_mcp(order_id: str) -> dict:
    """Call the MCP tool get_order_status over Streamable HTTP."""
    client_ctx = streamablehttp_client(ORDER_MCP_URL)
    read_stream, write_stream, _ = await client_ctx.__aenter__()
    session_ctx = ClientSession(read_stream, write_stream)
    session = await session_ctx.__aenter__()

    try:
        await session.initialize()
        result = await session.call_tool("get_order_status", {"order_id": order_id})
        # result.content is typically a JSON-like dict
        return result.content  # type: ignore[return-value]
    finally:
        await session_ctx.__aexit__(None, None, None)
        await client_ctx.__aexit__(None, None, None)
