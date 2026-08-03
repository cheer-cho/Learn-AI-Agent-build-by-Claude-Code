"""Optional LangSmith mirror for the local tracer.

The local JSONL tracer is the *source of truth* and works with no account. This
bridge is pure upside: when a learner has a free ``LANGSMITH_API_KEY`` in
``.env``, the same runs also appear in the LangSmith UI (projects → runs → the
per-step waterfall), which is a far nicer debugging surface than a JSONL file.

Contract the tests rely on:

- :func:`enabled` is a plain env check (``LANGSMITH_API_KEY`` present, tracing not
  force-disabled). No key → disabled → every method here is a silent no-op.
- **Nothing in the test suite ever requires this bridge.** It is best-effort:
  any import or network error degrades to disabled rather than raising, so the
  local trace is never lost to a LangSmith problem.

We read env vars directly here (this package never edits ``config.py``). The
LangSmith SDK's own client also reads ``LANGSMITH_API_KEY`` / ``LANGSMITH_PROJECT``
from the environment, so a configured ``.env`` is all that is needed.

API note (verified against langsmith 0.10.15): we use the low-level
``Client.create_run(name, inputs, run_type, id=..., ...)`` then
``Client.update_run(run_id, outputs=..., end_time=..., error=...)`` — the same
two-call pattern the ``@traceable`` decorator wraps. We pass an explicit ``id``
(the local ``run_id``) so a run is easy to correlate across the JSONL log and the
UI, and ``create_run`` accepts ``id`` via its ``**kwargs``.
"""

from __future__ import annotations

import datetime
import os
from typing import Any


def enabled() -> bool:
    """True when LangSmith mirroring should be attempted.

    Requires a non-empty ``LANGSMITH_API_KEY`` and that tracing is not explicitly
    turned off via ``LANGSMITH_TRACING=false``. Kept as a free function so both
    the tracer and the labs can cheaply ask "is the live path on?".
    """
    if os.getenv("LANGSMITH_TRACING", "").strip().lower() == "false":
        return False
    return bool(os.getenv("LANGSMITH_API_KEY", "").strip())


class LangSmithBridge:
    """A best-effort mirror of local runs into LangSmith.

    Construct one and pass it to ``LocalTracer(path, bridge=bridge)``; the tracer
    calls :meth:`mirror` with each written record. When :func:`enabled` is
    ``False`` the bridge holds no client and every call returns immediately.
    """

    def __init__(self, project: str | None = None):
        self.project = project or os.getenv("LANGSMITH_PROJECT", "techcorp-agent")
        self._client: Any | None = None
        if enabled():
            self._client = self._make_client()

    @staticmethod
    def _make_client() -> Any | None:
        """Construct a LangSmith ``Client``, or ``None`` on any failure."""
        try:
            from langsmith import Client

            return Client()  # reads LANGSMITH_API_KEY / endpoint from the environment
        except Exception:  # noqa: BLE001 - a missing/broken SDK just disables the mirror
            return None

    @property
    def active(self) -> bool:
        """True only when a client was actually constructed."""
        return self._client is not None

    def mirror(self, record: dict[str, Any]) -> None:
        """Mirror one local trace record (see ``Run.to_record``) to LangSmith.

        Best-effort: any error is swallowed so the local trace — already written
        by the time this runs — is never compromised by a LangSmith outage.
        """
        if self._client is None:
            return
        try:
            self._create_and_finish(record)
        except Exception:  # noqa: BLE001 - the local JSONL trace is the source of truth
            return

    def _create_and_finish(self, record: dict[str, Any]) -> None:
        """The two-call create/update pattern against the 0.10.15 SDK."""
        run_id = record["run_id"]
        now = datetime.datetime.now(datetime.UTC)
        # Nested steps become the run's events; the SDK renders them in the UI.
        events = [
            {"name": step.get("node", "step"), "data": step.get("data")}
            for step in record.get("steps", [])
        ]
        self._client.create_run(
            name=record.get("name", "techcorp-agent"),
            inputs=record.get("inputs", {}),
            run_type="chain",
            id=run_id,
            project_name=self.project,
            start_time=now,
            extra={"metadata": {"token_usage": record.get("token_usage", {})}},
        )
        self._client.update_run(
            run_id,
            outputs={"output": record.get("output")},
            events=events,
            error=record.get("error"),
            end_time=now,
        )
