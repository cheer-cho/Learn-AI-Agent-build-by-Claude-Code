"""A mock order-status lookup tool.

Reads ``data/orders/orders.json`` (mock data — no real customers, aliases only)
and returns typed order info. This is deliberately read-only: it never mutates
an order. An unknown order id is an ordinary, expected outcome — it returns a
``ToolResult`` failure with a helpful message, NOT an exception, so the agent
can relay "no such order" to the user gracefully.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from techcorp_agent.config import get_settings
from techcorp_agent.tools.base import ToolResult, ToolSpec

ORDER_LOOKUP_TOOL_NAME = "order_lookup"


class Order(BaseModel):
    """One mock order record."""

    order_id: str
    customer_alias: str
    status: str
    last_update: str
    estimated_delivery: str | None = None
    items: list[str] = Field(default_factory=list)
    support_action: str = "none"


def _orders_path() -> Path:
    return get_settings().data_dir / "orders" / "orders.json"


@lru_cache(maxsize=8)
def _load_orders(path: str) -> dict[str, Order]:
    """Load and index orders by id. Cached per path so the file is read once."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["order_id"]: Order(**row) for row in raw.get("orders", [])}


def lookup_order(order_id: str, orders_path: Path | None = None) -> Order | None:
    """Return the matching ``Order`` or ``None`` if the id is unknown.

    Order ids are matched case-insensitively and whitespace-trimmed so
    'tc-1234 ' still resolves.
    """
    path = orders_path or _orders_path()
    orders = _load_orders(str(path))
    return orders.get(order_id.strip().upper())


def format_order(order: Order) -> str:
    lines = [
        f"Order {order.order_id}: status {order.status}",
        f"last update: {order.last_update}",
    ]
    if order.estimated_delivery:
        lines.append(f"estimated delivery: {order.estimated_delivery}")
    if order.items:
        lines.append(f"items: {', '.join(order.items)}")
    if order.support_action and order.support_action != "none":
        lines.append(f"support action: {order.support_action}")
    return "\n".join(lines)


class OrderLookupArgs(BaseModel):
    order_id: str = Field(..., description="A TechCorp order id, e.g. 'TC-1234'.")


def _run(args: OrderLookupArgs) -> ToolResult:
    order = lookup_order(args.order_id)
    if order is None:
        return ToolResult.failure(
            ORDER_LOOKUP_TOOL_NAME,
            f"No order found with id '{args.order_id}'. Double-check the id "
            "(format TC-####) or ask the customer to confirm it.",
        )
    return ToolResult.success(ORDER_LOOKUP_TOOL_NAME, format_order(order))


def make_order_lookup_tool() -> ToolSpec:
    """A read-only order-status lookup over the mock order database."""
    return ToolSpec(
        name=ORDER_LOOKUP_TOOL_NAME,
        description=(
            "Look up the current status of a specific TechCorp order by its id "
            "(format TC-####). Use when the user names or asks about a particular "
            "order — 'where is TC-1234', 'what's going on with my order'. Do NOT "
            "use for general policy questions or math."
        ),
        args_schema=OrderLookupArgs,
        func=_run,
    )
