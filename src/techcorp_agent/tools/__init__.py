"""TechCorp agent tools: read-only capabilities the agent can route to.

Public surface reused by Modules 11, 13, 14, 18, and 22:

- ``ToolSpec`` / ``ToolResult`` — the tool definition and outcome primitives.
- ``make_calculator_tool`` / ``make_order_lookup_tool`` /
  ``make_document_search_tool`` — factory functions building each tool.
- ``route_question`` / ``keyword_route`` / ``run_tool`` — LLM routing with a
  deterministic keyword fallback, plus safe (validated, timeout-guarded)
  execution.

All tools here are read-only. Write-capable tools and human-approval gates
arrive in Module 16.
"""

from techcorp_agent.tools.base import ToolResult, ToolSpec
from techcorp_agent.tools.calculator import (
    CALCULATOR_TOOL_NAME,
    CalculatorArgs,
    CalculatorError,
    evaluate,
    make_calculator_tool,
)
from techcorp_agent.tools.orders import (
    ORDER_LOOKUP_TOOL_NAME,
    Order,
    OrderLookupArgs,
    lookup_order,
    make_order_lookup_tool,
)
from techcorp_agent.tools.router import (
    NO_TOOL,
    keyword_route,
    route_question,
    run_tool,
)
from techcorp_agent.tools.search_docs import (
    SEARCH_DOCS_TOOL_NAME,
    DocumentSearchArgs,
    make_document_search_tool,
)

__all__ = [
    "ToolResult",
    "ToolSpec",
    "CalculatorArgs",
    "CalculatorError",
    "CALCULATOR_TOOL_NAME",
    "evaluate",
    "make_calculator_tool",
    "Order",
    "OrderLookupArgs",
    "ORDER_LOOKUP_TOOL_NAME",
    "lookup_order",
    "make_order_lookup_tool",
    "DocumentSearchArgs",
    "SEARCH_DOCS_TOOL_NAME",
    "make_document_search_tool",
    "NO_TOOL",
    "keyword_route",
    "route_question",
    "run_tool",
]
