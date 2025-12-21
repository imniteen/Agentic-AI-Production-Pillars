from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv(override=True)


# Minimal in-memory "database"
ORDERS: dict[str, Dict[str, Any]] = {
    "ORD-123": {"status": "shipped", "eta_days": 2},
    "ORD-456": {"status": "processing", "eta_days": 5},
    "ORD-789": {"status": "delivered", "eta_days": 0},
}

mcp = FastMCP(
    name="OrderServiceMCP",
    host="127.0.0.1",
    port=8002,
)


@mcp.tool(
    name="get_order_status",
    description="Look up an order status by order id",
    structured_output=True,
)
def get_order_status(order_id: str) -> Dict[str, Any]:
    """
    Return order status info for a given order id.
    This is intentionally simplistic for the demo.
    """
    order = ORDERS.get(order_id)
    if not order:
        return {
            "found": False,
            "order_id": order_id,
        }

    return {
        "found": True,
        "order_id": order_id,
        **order,
    }


if __name__ == "__main__":
    # Expose tools via HTTP using Streamable HTTP transport
    # Final URL: http://127.0.0.1:8002/mcp
    mcp.run(transport="streamable-http", mount_path="")