"""Offline smoke test for the production service — no server, no network, no key.

Run it:

    uv run python course/21_production_deployment/solution/smoke.py

It drives the real FastAPI app (``apps.api.main:app``) through FastAPI's
``TestClient``, which runs the whole request path in-process — including the
lifespan handler that builds the index + agent once. It exercises liveness,
readiness, a grounded question, a calculator question, an unknown order, a
malformed request, and the SSE stream, printing a compact PASS/FAIL line for
each. This is the same behavior ``tests/test_api.py`` asserts, packaged as a
script a learner can eyeball.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run against the offline mock LLM and make ``apps`` importable from the repo root.
os.environ.setdefault("TECHCORP_OFFLINE", "true")
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.api.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    passed = True
    with TestClient(app) as client:
        r = client.get("/health")
        passed &= _check(
            "GET /health is 200 ok", r.status_code == 200 and r.json() == {"status": "ok"}
        )

        r = client.get("/ready")
        passed &= _check(
            "GET /ready is ready", r.status_code == 200 and r.json() == {"ready": True}
        )

        r = client.post("/chat", json={"question": "What is the remote work policy?"})
        body = r.json()
        passed &= _check(
            "POST /chat policy question answers",
            r.status_code == 200 and bool(body["answer"].strip()) and "conversation_id" in body,
            f"route={body.get('route')}",
        )

        r = client.post("/chat", json={"question": "What is 2 + 2?"})
        passed &= _check(
            "POST /chat calculator routes correctly",
            r.json().get("route") == "calculator" and "4" in r.json().get("answer", ""),
        )

        r = client.post("/chat", json={"question": "Where is order TC-9999?"})
        passed &= _check(
            "POST /chat unknown order degrades (no 500)",
            r.status_code == 200 and "TC-9999" in r.json().get("answer", ""),
        )

        r = client.post("/chat", json={})
        passed &= _check("POST /chat malformed request is 422", r.status_code == 422)

        r = client.post("/chat/stream", json={"question": "What is the remote work policy?"})
        frames = r.text.count("data:")
        passed &= _check(
            "POST /chat/stream yields multiple SSE frames",
            r.status_code == 200 and frames > 1 and "event: answer" in r.text,
            f"frames={frames}",
        )

    print()
    print("SMOKE OK — the service is deployable." if passed else "SMOKE FAILED — see above.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
