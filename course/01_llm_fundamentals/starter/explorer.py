"""Module 01 starter — token-and-context explorer.

Your job: implement the four functions marked with `# TODO:` below, following
the tasks in ../lab.md. The file already runs:

    uv run python course/01_llm_fundamentals/starter/explorer.py

It prints which steps still need work and demonstrates each one you finish.
Check your progress with:

    uv run pytest course/01_llm_fundamentals/tests/test_my_work.py -q
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

    tiktoken downloads its vocabulary file on first use, so this can fail on a
    machine that has never been online. Provided for you — call it from
    count_tokens() and handle the None case.
    """
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def count_tokens(text: str) -> int:
    """Return the number of tokens in `text`.

    Requirements (Task 1 in lab.md):
    - Use the tiktoken encoding from _load_encoding() when it is available.
    - If the encoding is None (or loading raised), fall back to the heuristic
      of roughly 4 characters per token: max(1, len(text) // 4).
    - Always return a positive int.
    """
    # TODO: Get the encoding via _load_encoding(); if you have one, return the
    #       length of its encode(text) result.
    # TODO: Otherwise return the heuristic estimate max(1, len(text) // 4).
    raise NotImplementedError("Task 1: implement count_tokens")


def add_noise(prompt: str, n_sentences: int) -> str:
    """Prepend `n_sentences` irrelevant sentences to `prompt` (Task 3 in lab.md).

    Requirements:
    - Cycle through NOISE_SENTENCES (use modulo) so n_sentences may exceed
      the list length.
    - Keep the original prompt intact at the END of the returned string.
    - If n_sentences <= 0, return the prompt unchanged.
    """
    # TODO: Build the list of noise sentences, join them and the prompt with
    #       spaces, and return the combined string.
    raise NotImplementedError("Task 3: implement add_noise")


def compare_with_and_without_noise(
    client, question: str, n_noise: int = 8
) -> tuple[ChatResult, ChatResult]:
    """Ask `question` twice — clean, then noisy — and return both results (Task 4).

    Requirements:
    - First call: client.complete() with a single user ChatMessage containing
      the plain question.
    - Second call: the same question wrapped by add_noise(question, n_noise).
    - Return (clean_result, noisy_result).
    """
    # TODO: Make the clean call.
    # TODO: Make the noisy call.
    # TODO: Return both ChatResults as a tuple.
    raise NotImplementedError("Task 4: implement compare_with_and_without_noise")


def enforce_budget(text: str, max_tokens: int, mode: str = "reject") -> str:
    """Keep `text` within `max_tokens` (Task 5 in lab.md).

    Requirements:
    - Unknown modes raise ValueError (only "reject" and "truncate" exist).
    - Text already within budget is returned unchanged.
    - mode="reject": raise ValueError with a message that states the actual
      token count, the budget, and what the caller can do about it.
    - mode="truncate": return a shortened text that fits the budget. With the
      tiktoken encoding, decode the first max_tokens tokens; without it, keep
      the first max_tokens * 4 characters.
    """
    # TODO: Validate mode before doing anything else.
    # TODO: Count tokens; return text unchanged if it fits.
    # TODO: Implement "reject" (raise ValueError with an actionable message).
    # TODO: Implement "truncate" (exact via encoding, else the ~4 chars/token cut).
    raise NotImplementedError("Task 5: implement enforce_budget")


def main() -> None:
    settings = get_settings()
    print("Module 01 — Token & Context Explorer (starter)")
    mode = "offline (deterministic mock)" if settings.offline else f"live ({settings.openai_model})"
    print(f"Client mode: {mode}\n")

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

    def show_token_report() -> None:
        print(f"  {count_tokens(APPLE_QUESTION)} tokens in: {APPLE_QUESTION}")

    def show_noise_report() -> None:
        print(f"  with 8 noise sentences: {count_tokens(add_noise(APPLE_QUESTION, 8))} tokens")

    def show_comparison() -> None:
        clean, noisy = compare_with_and_without_noise(client, APPLE_QUESTION)
        print(f"  clean: {clean.content!r}")
        print(f"  noisy: {noisy.content!r}")

    def show_budget() -> None:
        print(f"  {enforce_budget(add_noise(APPLE_QUESTION, 8), 40, mode='truncate')!r}")

    steps = [
        ("Task 1/2 — token report", show_token_report),
        ("Task 3 — noise report", show_noise_report),
        ("Task 4 — compare responses", show_comparison),
        ("Task 5 — budget (truncate to 40 tokens)", show_budget),
    ]
    for label, step in steps:
        print(label)
        try:
            step()
        except NotImplementedError as todo:
            print(f"  [not done yet] {todo}")
        print()


if __name__ == "__main__":
    main()
