"""Tool primitives shared across the agent modules (11, 13, 14, 18, 22).

A *tool* is a named capability the agent can invoke instead of answering from
the model's own weights: arithmetic, a document lookup, an order query. Two
small models carry everything the router and the agent need:

- ``ToolSpec`` — the *definition* the LLM sees when it decides what to call.
  Its ``description`` is load-bearing: the model routes on the description, not
  on the function body, so the text must be precise enough to tell one tool
  apart from the others (see Module 11 concepts).
- ``ToolResult`` — the *normalized outcome* of running a tool. Every tool
  returns one of these — success or failure — so the agent loop never has to
  catch exceptions from tool internals; a failed tool is data, not a crash.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """The normalized outcome of running one tool.

    ``ok`` is the single field the agent branches on. On success ``output`` is
    the user-facing text and ``error`` is ``None``; on failure ``error`` is a
    short, actionable message and ``output`` is empty. Tools never raise past
    their own boundary — they return ``ok=False`` instead.
    """

    tool_name: str
    ok: bool
    output: str = ""
    error: str | None = None

    @classmethod
    def success(cls, tool_name: str, output: str) -> "ToolResult":
        return cls(tool_name=tool_name, ok=True, output=output, error=None)

    @classmethod
    def failure(cls, tool_name: str, error: str) -> "ToolResult":
        return cls(tool_name=tool_name, ok=False, output="", error=error)


class ToolSpec(BaseModel):
    """A tool the agent can select and call.

    ``args_schema`` is a Pydantic model class describing the tool's inputs;
    validating raw arguments against it turns a missing/ill-typed argument into
    a clean validation error (a ``ToolResult`` failure) instead of a ``TypeError``
    deep inside the tool. ``func`` receives the validated model and returns a
    ``ToolResult``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str = Field(
        ...,
        description=(
            "What the tool does and when to pick it — written for an LLM to "
            "distinguish this tool from the others. Selection quality depends "
            "on this text more than on the code."
        ),
    )
    args_schema: type[BaseModel]
    func: Callable[[BaseModel], ToolResult]

    def run(self, raw_args: dict[str, Any]) -> ToolResult:
        """Validate ``raw_args`` against ``args_schema`` and invoke ``func``.

        A validation failure (missing or wrong-typed argument) becomes a
        ``ToolResult`` failure so the agent loop stays exception-free.
        """
        from pydantic import ValidationError

        try:
            args = self.args_schema(**raw_args)
        except ValidationError as exc:
            missing = ", ".join(
                str(err["loc"][0]) for err in exc.errors() if err["type"] == "missing"
            )
            detail = f"missing required argument(s): {missing}" if missing else "invalid arguments"
            return ToolResult.failure(self.name, f"Cannot run '{self.name}' — {detail}.")
        return self.func(args)
