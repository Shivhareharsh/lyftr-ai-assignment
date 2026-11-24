from unittest.mock import MagicMock, patch

import pytest

from app import llm


@pytest.fixture(autouse=True)
def clear_cache():
    llm.response_cache.clear()
    yield
    llm.response_cache.clear()


def make_response(
    content="test response",
    input_tokens=10,
    output_tokens=5,
):
    response = MagicMock()

    response.choices[0].message.content = content
    response.usage.prompt_tokens = input_tokens
    response.usage.completion_tokens = output_tokens

    return response


def test_cache_key_is_deterministic():
    messages = [
        {
            "role": "system",
            "content": "You are helpful.",
        },
        {
            "role": "user",
            "content": "Hello",
        },
    ]

    first = llm.create_cache_key(messages)
    second = llm.create_cache_key(messages)

    assert first == second


def test_live_inference():
    messages = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    fake_response = make_response(
        content="Hello back",
        input_tokens=12,
        output_tokens=4,
    )

    with patch.object(
        llm,
        "API_KEYS",
        ["fake-key-1", "fake-key-2"],
    ):
        with patch(
            "app.llm.completion",
            return_value=fake_response,
        ):
            result = llm.generate_reply(messages)

    assert result["reply"] == "Hello back"
    assert result["resolution_source"] == "LIVE_INFERENCE"
    assert result["input_tokens"] == 12
    assert result["output_tokens"] == 4
    assert result["key_id"] == "key_1"
    assert result["fallback_attempts"] == 0


def test_cache_hit_preserves_usage():
    messages = [
        {
            "role": "user",
            "content": "Explain caching",
        }
    ]

    fake_response = make_response(
        content="Caching stores reusable results.",
        input_tokens=15,
        output_tokens=7,
    )

    with patch.object(
        llm,
        "API_KEYS",
        ["fake-key-1"],
    ):
        with patch(
            "app.llm.completion",
            return_value=fake_response,
        ) as mocked_completion:

            first = llm.generate_reply(messages)
            second = llm.generate_reply(messages)

    assert first["resolution_source"] == "LIVE_INFERENCE"

    assert second["resolution_source"] == "LLM_CACHE"
    assert second["reply"] == first["reply"]

    assert (
        second["input_tokens"]
        == first["input_tokens"]
    )

    assert (
        second["output_tokens"]
        == first["output_tokens"]
    )

    assert second["key_id"] is None
    assert second["fallback_attempts"] == 0

    assert mocked_completion.call_count == 1


def test_failover_to_second_key():
    messages = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    fake_response = make_response(
        content="Failover works",
        input_tokens=9,
        output_tokens=3,
    )

    with patch.object(
        llm,
        "API_KEYS",
        ["fake-key-1", "fake-key-2"],
    ):
        with patch(
            "app.llm.completion",
            return_value=fake_response,
        ):
            result = llm.generate_reply(
                messages,
                simulate_failure="key_1=429",
            )

    assert result["reply"] == "Failover works"
    assert result["key_id"] == "key_2"
    assert result["fallback_attempts"] == 1
    assert result["resolution_source"] == "LIVE_INFERENCE"


def test_all_keys_fail():
    messages = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    with patch.object(
        llm,
        "API_KEYS",
        ["fake-key-1", "fake-key-2"],
    ):
        with pytest.raises(
            llm.AllProvidersUnavailable
        ):
            llm.generate_reply(
                messages,
                simulate_failure="*=503",
            )


def test_failure_simulation_parser():
    failures = llm.parse_simulated_failures(
        "key_1=429,key_2=503"
    )

    assert failures == {
        "key_1": 429,
        "key_2": 503,
    }


def test_invalid_simulation_status_is_ignored():
    failures = llm.parse_simulated_failures(
        "key_1=400,key_2=abc"
    )

    assert failures == {}