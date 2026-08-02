import pytest

from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage


def messages(user_text: str) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are the TechCorp assistant."),
        ChatMessage(role="user", content=user_text),
    ]


def test_scripted_responses_return_in_order():
    client = MockLLMClient(responses=["first", "second"])
    assert client.complete(messages("a")).content == "first"
    assert client.complete(messages("b")).content == "second"


def test_calls_are_recorded():
    client = MockLLMClient(responses=["ok"])
    client.complete(messages("what is the dress code?"))
    assert len(client.calls) == 1
    assert client.calls[0][1].content == "what is the dress code?"


def test_default_mode_is_deterministic():
    first = MockLLMClient().complete(messages("hello"))
    second = MockLLMClient().complete(messages("hello"))
    assert first.content == second.content


def test_usage_is_always_reported():
    result = MockLLMClient(responses=["ok"]).complete(messages("hi"))
    assert result.usage is not None
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


def test_empty_messages_rejected():
    with pytest.raises(ValueError):
        MockLLMClient().complete([])
