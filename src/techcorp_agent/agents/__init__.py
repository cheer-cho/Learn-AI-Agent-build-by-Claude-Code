"""TechCorp multi-agent system (Module 18).

A supervisor coordinator over three focused specialists, built by *composing*
the components from earlier modules (RAG pipeline, tools, vector store) — it
reimplements none of them. The package exists to teach one honest lesson:
multi-agent is a trade-off, not an upgrade, and ``comparison`` is how you tell
which side of the trade you are on.

- :mod:`~techcorp_agent.agents.specialists` — Policy / Support / Orders
  specialists (focused prompts, small tool sets).
- :mod:`~techcorp_agent.agents.supervisor`  — ``SupervisorAgent``: route → hand
  off → synthesize, with graceful failure.
- :mod:`~techcorp_agent.agents.comparison`  — ``run_comparison`` /
  ``write_comparison_report``: measure supervisor vs single agent truthfully.
"""

from techcorp_agent.agents.comparison import (
    RunOutcome,
    SystemMeasurement,
    run_comparison,
    single_agent_outcome,
    supervisor_outcome,
    write_comparison_report,
)
from techcorp_agent.agents.specialists import (
    OrdersSpecialist,
    PolicySpecialist,
    SpecialistResult,
    SupportSpecialist,
)
from techcorp_agent.agents.supervisor import SupervisorAgent, SupervisorResult

__all__ = [
    "OrdersSpecialist",
    "PolicySpecialist",
    "RunOutcome",
    "SpecialistResult",
    "SupervisorAgent",
    "SupervisorResult",
    "SupportSpecialist",
    "SystemMeasurement",
    "run_comparison",
    "single_agent_outcome",
    "supervisor_outcome",
    "write_comparison_report",
]
