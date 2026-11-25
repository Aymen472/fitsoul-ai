"""Unit tests for the centralized Gemini client wrapper and AI tracing."""

import base64
import json

import httpx
import pytest
from pydantic import BaseModel, Field

from app.ai import (
    AITraceEvent,
    GeminiAuthError,
    GeminiClient,
    GeminiClientError,
    GeminiResponseFormatError,
    LangfuseTraceSink,
    estimate_cost_usd,
)


class _SampleMeal(BaseModel):
    dish: str
    servings: float = Field(gt=0)


def _gemini_ok_response(
    text: str,
    *,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> httpx.Response:
    payload = {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": completion_tokens,
            "totalTokenCount": prompt_tokens + completion_tokens,
        },
    }
    return httpx.Response(200, text=json.dumps(payload))


def test_missing_api_key_raises_without_http_call() -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _gemini_ok_response("ok")

    traces: list[AITraceEvent] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = GeminiClient(api_key="   ", client=http_client, trace_sink=traces.append)
        with pytest.raises(GeminiAuthError, match="not configured"):
            client.generate_text("Assalam o alaikum")

    assert called is False
    assert len(traces) == 1
    assert traces[0].success is False


def test_generate_text_headers_system_instruction_and_usage() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key_header"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _gemini_ok_response("Wa alaikum assalam!", prompt_tokens=1000, completion_tokens=500)

    traces: list[AITraceEvent] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = GeminiClient(
            api_key="secret-test-key",
            client=http_client,
            trace_sink=traces.append,
        )
        result = client.generate_text(
            "Hello coach",
            system_instruction="Respond warmly in Roman Urdu.",
            metadata={"user_id": "u-1"},
        )

    assert "secret-test-key" not in str(captured["url"])
    assert str(captured["url"]).endswith("/models/gemini-2.5-flash:generateContent")
    assert captured["api_key_header"] == "secret-test-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["systemInstruction"] == {"parts": [{"text": "Respond warmly in Roman Urdu."}]}

    assert result.text == "Wa alaikum assalam!"
    assert result.usage.prompt_tokens == 1000
    assert result.usage.completion_tokens == 500
    assert result.usage.total_tokens == 1500
    assert result.usage.estimated_cost_usd == estimate_cost_usd("gemini-2.5-flash", 1000, 500)
    assert result.usage.latency_ms >= 0

    assert len(traces) == 1
    assert traces[0].success is True
    assert traces[0].metadata == {"user_id": "u-1"}


@pytest.mark.parametrize(
    "raw_json",
    [
        '{"dish": "Daal Moong", "servings": 1.5}',
        '```json\n{"dish": "Daal Moong", "servings": 1.5}\n```',
    ],
)
def test_generate_structured_validates_pydantic_schema(raw_json: str) -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content.decode("utf-8"))
        return _gemini_ok_response(raw_json)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        meal, usage = client.generate_structured("Suggest lunch", _SampleMeal)

    gen_config = captured_body["generationConfig"]
    assert isinstance(gen_config, dict)
    assert gen_config["responseMimeType"] == "application/json"
    assert gen_config["responseJsonSchema"] == _SampleMeal.model_json_schema()
    assert meal == _SampleMeal(dish="Daal Moong", servings=1.5)
    assert usage.total_tokens == 150


@pytest.mark.parametrize("bad_output", ["not json at all", '{"dish": "Roti", "servings": -2}'])
def test_generate_structured_invalid_output_raises_and_traces(bad_output: str) -> None:
    traces: list[AITraceEvent] = []
    transport = httpx.MockTransport(lambda _: _gemini_ok_response(bad_output))

    with httpx.Client(transport=transport) as http_client:
        client = GeminiClient(api_key="test-key", client=http_client, trace_sink=traces.append)
        with pytest.raises(GeminiResponseFormatError):
            client.generate_structured("Suggest lunch", _SampleMeal)

    assert len(traces) == 1
    assert traces[0].success is False
    assert traces[0].usage is not None
    assert traces[0].usage.total_tokens == 150


def test_analyze_image_encodes_inline_data_and_validates() -> None:
    sample_bytes = b"\xff\xd8\xff\xe0fake-jpeg-data"
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content.decode("utf-8"))
        return _gemini_ok_response('{"dish": "Chicken Karahi", "servings": 1.0}')

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        meal, _ = client.analyze_image(
            image_bytes=sample_bytes,
            mime_type="image/jpeg",
            prompt="Identify this meal",
            response_schema=_SampleMeal,
        )

    assert meal == _SampleMeal(dish="Chicken Karahi", servings=1.0)
    parts = captured_body["contents"][0]["parts"]  # type: ignore[index]
    assert parts[0] == {"text": "Identify this meal"}
    assert parts[1] == {
        "inlineData": {
            "mimeType": "image/jpeg",
            "data": base64.b64encode(sample_bytes).decode("ascii"),
        }
    }


def test_analyze_image_invalid_inputs_raise_value_error() -> None:
    client = GeminiClient(api_key="test-key", trace_sink=lambda _: None)

    with pytest.raises(ValueError, match="image_bytes"):
        client.analyze_image(b"", "image/jpeg", "Identify", _SampleMeal)
    with pytest.raises(ValueError, match="mime_type"):
        client.analyze_image(b"abc", "text/plain", "Identify", _SampleMeal)


def test_retries_transient_errors_then_succeeds() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, text="Rate limited")
        if attempts == 2:
            return httpx.Response(503, text="Service unavailable")
        return _gemini_ok_response("Recovered response")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = GeminiClient(
            api_key="test-key",
            max_retries=3,
            retry_backoff_seconds=0.5,
            client=http_client,
            trace_sink=lambda _: None,
            sleep_fn=sleeps.append,
        )
        res = client.generate_text("Hi")

    assert res.text == "Recovered response"
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_auth_and_client_4xx_errors_do_not_retry() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, text="Unauthorized")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = GeminiClient(
            api_key="bad-key",
            max_retries=3,
            client=http_client,
            trace_sink=lambda _: None,
            sleep_fn=sleeps.append,
        )
        with pytest.raises(GeminiAuthError, match="401"):
            client.generate_text("Hi")

    assert attempts == 1
    assert sleeps == []


def test_exhausted_503_and_timeouts_raise_client_error() -> None:
    sleeps: list[float] = []

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout_handler)) as http_client:
        client = GeminiClient(
            api_key="test-key",
            max_retries=3,
            retry_backoff_seconds=0.25,
            client=http_client,
            trace_sink=lambda _: None,
            sleep_fn=sleeps.append,
        )
        with pytest.raises(GeminiClientError, match="network error"):
            client.generate_text("Hi")

    assert sleeps == [0.25, 0.5]

    sleeps.clear()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, text="Down"))
    ) as http_client:
        client = GeminiClient(
            api_key="test-key",
            max_retries=3,
            retry_backoff_seconds=0.25,
            client=http_client,
            trace_sink=lambda _: None,
            sleep_fn=sleeps.append,
        )
        with pytest.raises(GeminiClientError, match="503"):
            client.generate_text("Hi")

    assert sleeps == [0.25, 0.5]


def test_estimate_cost_usd_flash_vs_pro() -> None:
    flash_cost = estimate_cost_usd("gemini-2.5-flash", prompt_tokens=1_000_000, completion_tokens=0)
    pro_cost = estimate_cost_usd(
        "gemini-2.5-pro", prompt_tokens=1_000_000, completion_tokens=1_000_000
    )

    assert flash_cost == 0.15
    assert pro_cost == 11.25


def test_langfuse_trace_sink_posts_and_swallows_http_errors() -> None:
    captured: dict[str, object] = {}

    def ok_handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(207, text='{"successes": []}')

    event = AITraceEvent(trace_name="meal_plan", model="gemini-2.5-flash", success=True)
    with httpx.Client(transport=httpx.MockTransport(ok_handler)) as http_client:
        sink = LangfuseTraceSink(
            public_key="pk-test",
            secret_key="sk-test",
            host="https://cloud.langfuse.com/",
            client=http_client,
        )
        sink(event)

    assert captured["url"] == "https://cloud.langfuse.com/api/public/ingestion"
    assert str(captured["auth"]).startswith("Basic ")
    batch = captured["body"]["batch"]  # type: ignore[index]
    assert [item["type"] for item in batch] == ["trace-create", "generation-create"]

    # Ensure Langfuse outage never breaks caller
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(500, text="Outage"))
    ) as fail_client:
        failing_sink = LangfuseTraceSink(
            public_key="pk-test",
            secret_key="sk-test",
            client=fail_client,
        )
        failing_sink(event)
