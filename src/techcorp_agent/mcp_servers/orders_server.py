"""TechCorp order-status exposed as an MCP server (order lookups over stdio).

Module 12 built a *calculator* MCP server; this is its sibling — the second
server Module 13 connects at the same time so learners can watch tool-name
collisions, namespacing, and routing across *two* servers. It exposes two typed
tools:

- ``get_order_status(order_id)`` — the current status of one order.
- ``list_recent_orders(limit)`` — a short list of known order ids and statuses.

The order data is the same mock database the in-process Module 11 tool reads
(``data/orders/orders.json`` — mock aliases only, no real customers). This
server does **not** re-implement the loading logic: it imports and reuses
:func:`techcorp_agent.tools.orders.lookup_order` so there is a single source of
truth for what an order is.

Errors are *expected outcomes*, not crashes. Looking up an unknown id such as
``TC-9999`` returns a tool result with ``is_error=True`` and a helpful message
(via a raised ``ValueError`` the MCP runtime converts) — the server process
stays alive and keeps serving, exactly like the calculator's divide-by-zero.

mcp 2.0 API note
----------------
The installed ``mcp`` package is version 2.0. Its high-level server class is
:class:`mcp.server.MCPServer`; decorate a plain typed function with
``@server.tool(...)`` and the JSON tool schema is derived from the type hints,
then serve it with ``server.run(transport="stdio")``.

Run standalone::

    uv run python -m techcorp_agent.mcp_servers.orders_server
"""

from mcp.server import MCPServer
from pydantic import BaseModel, Field

from techcorp_agent.tools.orders import _load_orders, _orders_path, lookup_order

server = MCPServer(
    name="techcorp-orders",
    instructions=(
        "Look up TechCorp order status by id, or list a few recent orders. "
        "Read-only mock data — no real customers."
    ),
)


class OrderStatus(BaseModel):
    """The full status record returned by ``get_order_status``.

    Declaring the return type as a model (rather than a bare ``dict``) makes the
    MCP runtime attach a machine-readable output schema and populate the
    result's ``structured_content`` — so callers get typed fields, not just a
    blob of text to re-parse.
    """

    order_id: str
    status: str
    last_update: str
    estimated_delivery: str | None = None
    items: list[str] = Field(default_factory=list)
    support_action: str = "none"


class OrderSummary(BaseModel):
    """One row of ``list_recent_orders`` — id + status only, no item detail."""

    order_id: str
    status: str
    last_update: str


class RecentOrders(BaseModel):
    """The ``list_recent_orders`` payload: a count and the trimmed rows."""

    count: int
    orders: list[OrderSummary] = Field(default_factory=list)


@server.tool(
    description=(
        "Look up the current status of one TechCorp order by its id "
        "(format TC-####, e.g. 'TC-1234'). Returns the status, last update "
        "timestamp, estimated delivery, items, and any open support action. "
        "An unknown id (e.g. 'TC-9999') is rejected with a helpful error "
        "instead of crashing. Use for a *specific* named order — not for math "
        "or general policy questions."
    ),
)
def get_order_status(order_id: str) -> OrderStatus:
    """Return the full status record for ``order_id``.

    Raises:
        ValueError: if the id is unknown. The MCP runtime turns this into a
            tool result with ``is_error=True`` and a human-readable message
            rather than letting the server die.
    """
    order = lookup_order(order_id)
    if order is None:
        raise ValueError(
            f"No order found with id '{order_id}'. Double-check the id "
            "(format TC-####) or ask the customer to confirm it."
        )
    return OrderStatus(
        order_id=order.order_id,
        status=order.status,
        last_update=order.last_update,
        estimated_delivery=order.estimated_delivery,
        items=list(order.items),
        support_action=order.support_action,
    )


@server.tool(
    description=(
        "List a few recent TechCorp orders (id + status), most-recently-updated "
        "first, up to `limit` (default 5). Use when the user asks 'what orders "
        "are there' or you need a valid order id to look up. Does not return "
        "full item detail — call get_order_status for one order's full record."
    ),
)
def list_recent_orders(limit: int = 5) -> RecentOrders:
    """Return up to ``limit`` known orders as id/status/last_update rows.

    Rows are sorted by ``last_update`` descending so the freshest orders lead.
    A non-positive ``limit`` yields an empty list rather than an error — asking
    for zero orders is a valid, if pointless, request.
    """
    orders = _load_orders(str(_orders_path()))
    rows = sorted(orders.values(), key=lambda o: o.last_update, reverse=True)
    trimmed = rows[: max(limit, 0)]
    return RecentOrders(
        count=len(trimmed),
        orders=[
            OrderSummary(order_id=o.order_id, status=o.status, last_update=o.last_update)
            for o in trimmed
        ],
    )


def main() -> None:
    """Run the orders server over stdio (blocking)."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
