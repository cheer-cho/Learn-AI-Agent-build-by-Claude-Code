"""A safe arithmetic tool.

The obvious implementation — ``eval(expression)`` — is also a remote-code
execution hole: ``__import__('os').system('rm -rf ~')`` is a perfectly valid
Python expression. This module never calls ``eval``. Instead it parses the
expression to an AST and walks it with a strict allowlist of node types, so
anything that is not plain arithmetic (names, attribute access, calls,
subscripts) is rejected before a single operation runs.

Supported: ``+ - * / % **``, unary minus, parentheses, integer/float
literals, and a light "percent phrasing" pre-pass so questions like
``"17.5% of 8400"`` become ``17.5/100*8400`` (= 1470).
"""

import ast
import operator
import re

# The only AST node types we allow. Anything else (Name, Call, Attribute,
# Subscript, ...) means the input is not plain arithmetic — reject it.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

# "X% of Y" -> "X/100*Y". Handles the most common natural-language percent form
# so the arithmetic that follows is ordinary. A bare trailing "X%" (not used as
# the modulo operator, i.e. not followed by another operand) -> "(X/100)".
_PERCENT_OF_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*of\s+", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%(?!\s*[.\d(])")

# Light natural-language phrasing so "125 multiplied by 48" or "what is 12 plus 3"
# become plain arithmetic. Order matters: multi-word phrases before single words.
_WORD_OPS = [
    (re.compile(r"\bmultiplied\s+by\b", re.IGNORECASE), "*"),
    (re.compile(r"\bdivided\s+by\b", re.IGNORECASE), "/"),
    (re.compile(r"\btimes\b", re.IGNORECASE), "*"),
    (re.compile(r"\bplus\b", re.IGNORECASE), "+"),
    (re.compile(r"\bminus\b", re.IGNORECASE), "-"),
    (re.compile(r"\bto the power of\b", re.IGNORECASE), "**"),
]
# Leading question framing we can safely strip ("what is", "calculate", "="...).
_STRIP_PREFIX_RE = re.compile(r"^\s*(what\s+is|calculate|compute|how much is)\b", re.IGNORECASE)


class CalculatorError(ValueError):
    """The expression was empty, malformed, unsafe, or undefined (e.g. /0)."""


def _normalize(expression: str) -> str:
    """Rewrite natural-language phrasing into plain arithmetic.

    "what is 125 multiplied by 48" -> "125*48";  "17.5% of 8400" -> "17.5/100* 8400";
    trailing "10%" -> "(10/100)". Currency symbols, commas, and a trailing '?'
    are stripped so shopper-style questions parse.
    """
    expression = _STRIP_PREFIX_RE.sub("", expression)
    expression = expression.replace("$", "").replace(",", "").rstrip("? ").strip()
    for pattern, symbol in _WORD_OPS:
        expression = pattern.sub(symbol, expression)
    expression = _PERCENT_OF_RE.sub(lambda m: f"{m.group(1)}/100*", expression)
    expression = _PERCENT_RE.sub(lambda m: f"({m.group(1)}/100)", expression)
    return expression


def _eval_node(node: ast.AST) -> float:
    if not isinstance(node, _ALLOWED_NODES):
        raise CalculatorError(
            f"unsupported expression element: {type(node).__name__} "
            "(only numbers and + - * / % ** parentheses are allowed)"
        )
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError(f"only numeric literals are allowed, got {node.value!r}")
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp):
        left, right = _eval_node(node.left), _eval_node(node.right)
        op = _BIN_OPS[type(node.op)]
        if isinstance(node.op, (ast.Div, ast.Mod)) and right == 0:
            raise CalculatorError("division by zero")
        return op(left, right)
    # Unreachable: _ALLOWED_NODES is exactly the set handled above.
    raise CalculatorError(f"unsupported expression element: {type(node).__name__}")


def evaluate(expression: str) -> float:
    """Safely evaluate an arithmetic ``expression`` and return a float.

    Raises ``CalculatorError`` for empty input, syntax errors, division by
    zero, or anything that is not plain arithmetic (names, calls, imports).
    """
    if not expression or not expression.strip():
        raise CalculatorError("empty expression")
    normalized = _normalize(expression)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"could not parse expression: {exc.msg}") from None
    return _eval_node(tree)


def _format_number(value: float) -> str:
    """Render 6000.0 as '6000' but keep 1470.5 as '1470.5'."""
    if value == int(value):
        return str(int(value))
    return str(round(value, 10))


# --- tool wiring -------------------------------------------------------------

from pydantic import BaseModel, Field  # noqa: E402

from techcorp_agent.tools.base import ToolResult, ToolSpec  # noqa: E402

CALCULATOR_TOOL_NAME = "calculator"


class CalculatorArgs(BaseModel):
    expression: str = Field(
        ...,
        description="An arithmetic expression, e.g. '125 * 48' or '17.5% of 8400'.",
    )


def _run(args: CalculatorArgs) -> ToolResult:
    try:
        value = evaluate(args.expression)
    except CalculatorError as exc:
        return ToolResult.failure(CALCULATOR_TOOL_NAME, f"Calculation failed: {exc}.")
    return ToolResult.success(CALCULATOR_TOOL_NAME, _format_number(value))


def make_calculator_tool() -> ToolSpec:
    """A read-only arithmetic tool. No I/O, no state — pure computation."""
    return ToolSpec(
        name=CALCULATOR_TOOL_NAME,
        description=(
            "Evaluate an arithmetic expression and return the number. Use for any "
            "math: sums, products, percentages ('17.5% of 8400'), multi-step "
            "calculations. Do NOT use for looking up facts, policies, or orders."
        ),
        args_schema=CalculatorArgs,
        func=_run,
    )
