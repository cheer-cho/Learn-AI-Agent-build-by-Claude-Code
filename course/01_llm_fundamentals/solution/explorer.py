"""Module 01 solution — token-and-context explorer.

Run it (works fully offline, no API key needed):

    uv run python course/01_llm_fundamentals/solution/explorer.py

It demonstrates four things:

1. Counting tokens (exact via tiktoken, heuristic fallback when offline).
2. Adding configurable irrelevant context ("noise") to a prompt.
3. Comparing model responses with and without that noise.
4. Enforcing a token budget by rejecting or truncating oversized input.
"""

from techcorp_agent.config import get_settings
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage, ChatResult

# The apple example from concepts.md: the answer is 16 no matter how much
# apple trivia surrounds the question.
APPLE_QUESTION = "Sally has 14 apples. Bob has 2 apples. How many apples do they have in total?"

# Irrelevant-but-plausible context. None of it changes the arithmetic.
NOISE_SENTENCES = [
    "Apples come in red, green, and yellow varieties.",
    "Granny Smith apples are famously tart and bright green.",
    "Some people think Fuji apples are the sweetest of all.",
    "The skin of a Red Delicious apple is a deep crimson color.",
    "Honeycrisp apples are known for their satisfying crunch.",
    "Golden Delicious apples turn from green to pale yellow as they ripen.",
    "Many bakers prefer tart apples because their flavor survives the oven.",
    "A ripe Gala apple smells faintly of flowers.",
]


def _load_encoding():
    """Load a tiktoken encoding, or return None if it cannot be loaded.

    tiktoken downloads its vocabulary file on first use. On a machine that has
    never been online, that download fails — so token counting must degrade
    gracefully instead of crashing the lab.
    """
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def count_tokens(text: str) -> int:
    """Number of tokens in `text` — exact if tiktoken is available, else ~len/4.

    The heuristic (about 4 characters per English token) is the same one the
    course's MockLLMClient uses, so offline numbers stay consistent.
    """
    try:
        encoding = _load_encoding()
    except Exception:
        encoding = None
    if encoding is not None:
        return len(encoding.encode(text))
    return max(1, len(text) // 4)


def add_noise(prompt: str, n_sentences: int) -> str:
    """Prepend `n_sentences` irrelevant apple facts to `prompt`.

    Cycles through NOISE_SENTENCES so any amount of noise can be generated.
    The original prompt is kept intact at the end, exactly as a careless
    copy-paste of "background material" would do.
    """
    if n_sentences <= 0:
        return prompt
    noise = [NOISE_SENTENCES[i % len(NOISE_SENTENCES)] for i in range(n_sentences)]
    return " ".join([*noise, prompt])


def compare_with_and_without_noise(
    client, question: str, n_noise: int = 8
) -> tuple[ChatResult, ChatResult]:
    """Ask `question` twice — clean, then buried under noise — and return both results.

    Returns (clean_result, noisy_result). The client is passed in so tests and
    the lab can use a scripted MockLLMClient offline and a real client live.
    """
    clean = client.complete([ChatMessage(role="user", content=question)])
    noisy_prompt = add_noise(question, n_noise)
    noisy = client.complete([ChatMessage(role="user", content=noisy_prompt)])
    return clean, noisy


def enforce_budget(text: str, max_tokens: int, mode: str = "reject") -> str:
    """Keep `text` within `max_tokens`.

    - mode="reject":   raise ValueError with an actionable message if over budget.
    - mode="truncate": cut the text down so it fits, and return it.

    Text already within budget is returned unchanged in either mode.
    """
    if mode not in ("reject", "truncate"):
        raise ValueError(f"Unknown mode {mode!r}: use 'reject' or 'truncate'.")
    tokens = count_tokens(text)
    if tokens <= max_tokens:
        return text
    if mode == "reject":
        raise ValueError(
            f"Input is {tokens} tokens but the budget is {max_tokens}. "
            f"Shorten the prompt by ~{tokens - max_tokens} tokens, raise the budget, "
            "or call enforce_budget(..., mode='truncate') to cut it automatically."
        )
    # mode == "truncate"
    encoding = _load_encoding()
    if encoding is not None:
        return encoding.decode(encoding.encode(text)[:max_tokens])
    # Heuristic fallback: ~4 characters per token.
    return text[: max_tokens * 4]


def _print_result(label: str, result: ChatResult) -> None:
    print(f"--- {label} ---")
    print(f"  response: {result.content}")
    if result.usage:
        print(
            f"  usage:    {result.usage.input_tokens} input tokens, "
            f"{result.usage.output_tokens} output tokens"
        )
    print()


def main() -> None:
    settings = get_settings()

    print("=" * 70)
    print("Module 01 — Token & Context Explorer")
    print("=" * 70)
    mode = "offline (deterministic mock)" if settings.offline else f"live ({settings.openai_model})"
    print(f"Client mode: {mode}\n")

    # 1) Token report for the clean question.
    print(f"Question: {APPLE_QUESTION}")
    print(f"Tokens:   {count_tokens(APPLE_QUESTION)}\n")

    # 2) Add noise and report again.
    n_noise = 8
    noisy_prompt = add_noise(APPLE_QUESTION, n_noise)
    print(f"Same question with {n_noise} irrelevant apple facts prepended:")
    print(f"  {noisy_prompt[:120]}...")
    print(f"Tokens:   {count_tokens(noisy_prompt)}  (was {count_tokens(APPLE_QUESTION)})\n")

    # 3) Compare responses. Offline we script the mock so the demonstration is
    #    readable; live, the model answers for itself.
    if settings.offline:
        client = MockLLMClient(
            responses=[
                "Sally has 14 apples and Bob has 2, so together they have 16 apples.",
                "There are many apple facts here. Counting the varieties mentioned "
                "(red, green, yellow, Granny Smith, Fuji...) — perhaps you mean "
                "those? If you mean Sally and Bob, they have 16 apples.",
            ]
        )
    else:
        client = get_llm_client(settings)

    clean, noisy = compare_with_and_without_noise(client, APPLE_QUESTION, n_noise=n_noise)
    _print_result("WITHOUT noise", clean)
    _print_result(f"WITH {n_noise} noise sentences", noisy)
    print("The correct total is 16 either way — the noise only added tokens,")
    print("cost, and a chance for the model to get distracted.\n")

    # 4) Budget demo: reject, then truncate.
    budget = 40
    print(f"--- Token budget demo (budget = {budget} tokens) ---")
    print(f"Noisy prompt is {count_tokens(noisy_prompt)} tokens.")
    try:
        enforce_budget(noisy_prompt, budget, mode="reject")
    except ValueError as err:
        print(f"  reject   -> ValueError: {err}")
    truncated = enforce_budget(noisy_prompt, budget, mode="truncate")
    print(f"  truncate -> kept {count_tokens(truncated)} tokens: {truncated!r}")
    print("\nNotice what truncation kept: the noise. The actual question was cut")
    print("off. Choosing WHAT to keep is the retrieval problem — see Level 2.")


if __name__ == "__main__":
    main()
