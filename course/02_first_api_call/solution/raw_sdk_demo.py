"""The same call as first_call.py, written directly against the raw `openai` SDK.

Purpose (referenced from concepts.md): see exactly what the course adapter in
`techcorp_agent.llm.openai_client` wraps for you. Application code in this
course never talks to the SDK directly — this file exists so you know what is
underneath the abstraction.

This demo needs a real provider. Without OPENAI_API_KEY it exits with a
friendly message instead of failing (use first_call.py for the offline path).

Run it:
    uv run python course/02_first_api_call/solution/raw_sdk_demo.py
"""

from techcorp_agent.config import get_settings


def main() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        print("No OPENAI_API_KEY configured — this demo talks to a real provider.")
        print("Set the key in .env and re-run. (solution/first_call.py works offline.)")
        return 0

    # Imported here so offline learners never need a working provider setup.
    from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI

    # 1. The client: API key proves who you are; base URL says which
    #    OpenAI-compatible endpoint to call (blank = api.openai.com).
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
    )

    # 2. The request: model identifier + role-tagged messages + generation knobs.
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "You are TechCorp's internal assistant."},
                {
                    "role": "user",
                    "content": "In one sentence, what should I do when a customer asks for a refund?",
                },
            ],
            temperature=0.0,
            max_tokens=settings.max_output_tokens,
        )
    except AuthenticationError:
        print("Authentication failed (401). Check OPENAI_API_KEY in .env — wrong or expired key.")
        return 1
    except APIConnectionError:
        print("Network error: could not reach the provider. Check connectivity / OPENAI_BASE_URL.")
        return 1
    except APIStatusError as exc:
        print(f"Provider returned HTTP {exc.status_code}. Check OPENAI_MODEL in .env.")
        return 1

    # 3. The response is a rich object, not a string — extract defensively:
    #    choices may be empty, and message.content may be None.
    choice = response.choices[0] if response.choices else None
    content = (choice.message.content or "") if choice else ""
    print("assistant:    ", content)
    print("model:        ", response.model)
    print("finish_reason:", choice.finish_reason if choice else "(no choices)")

    # 4. Usage is optional in the API contract.
    if response.usage is not None:
        print(
            f"tokens:        {response.usage.prompt_tokens} in / "
            f"{response.usage.completion_tokens} out / {response.usage.total_tokens} total"
        )
    else:
        print("tokens:        usage not reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
