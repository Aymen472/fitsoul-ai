"""Centralized Google Gemini API client with structured output, vision, retries, and tracing."""

import base64
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.tracing import AITraceEvent, AIUsage, TraceSink, build_default_trace_sink
from app.config import get_settings

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_FLASH_MODEL = "gemini-2.5-flash"
DEFAULT_PRO_MODEL = "gemini-2.5-pro"

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# USD per 1M tokens: (input_price, output_price)
MODEL_PRICING_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}


class GeminiClientError(Exception):
    """Base error raised when a Gemini API call fails."""


class GeminiAuthError(GeminiClientError):
    """Raised when the Gemini API key is missing or rejected (401/403)."""


class GeminiResponseFormatError(GeminiClientError):
    """Raised when Gemini returns empty text or invalid structured JSON."""


class AITextResponse(BaseModel):
    """Text completion result paired with usage and cost metrics."""

    text: str
    usage: AIUsage


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate call cost in USD from model token pricing."""
    input_price, output_price = MODEL_PRICING_PER_1M_TOKENS.get(
        model, MODEL_PRICING_PER_1M_TOKENS[DEFAULT_FLASH_MODEL]
    )
    cost = ((prompt_tokens * input_price) + (completion_tokens * output_price)) / 1_000_000
    return round(cost, 8)


def _strip_code_fences(raw_text: str) -> str:
    """Strip optional markdown code fences surrounding JSON output."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def _extract_text(payload: dict[str, Any]) -> str:
    """Extract concatenated text parts from the first Gemini response candidate."""
    candidates = payload.get("candidates") or []
    if not candidates:
        raise GeminiResponseFormatError("Gemini response contained no candidates")

    parts = candidates[0].get("content", {}).get("parts") or []
    text_chunks = [part["text"] for part in parts if isinstance(part.get("text"), str)]
    text = "".join(text_chunks).strip()
    if not text:
        raise GeminiResponseFormatError("Gemini response contained no text content")
    return text


def _extract_usage(payload: dict[str, Any], model: str, latency_ms: float) -> AIUsage:
    """Build an AIUsage summary from Gemini usageMetadata."""
    meta = payload.get("usageMetadata") or {}
    prompt_tokens = int(meta.get("promptTokenCount") or 0)
    completion_tokens = int(meta.get("candidatesTokenCount") or 0)
    total_tokens = int(meta.get("totalTokenCount") or (prompt_tokens + completion_tokens))
    return AIUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost_usd(model, prompt_tokens, completion_tokens),
        latency_ms=round(latency_ms, 2),
    )


class GeminiClient:
    """Single entry point for all Gemini text, structured JSON, and vision calls."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        pro_model: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        client: httpx.Client | None = None,
        trace_sink: TraceSink | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")

        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.gemini_api_key).strip()
        self.default_model = default_model or settings.gemini_flash_model or DEFAULT_FLASH_MODEL
        self.pro_model = pro_model or settings.gemini_pro_model or DEFAULT_PRO_MODEL
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._client = client
        self._trace_sink = trace_sink if trace_sink is not None else build_default_trace_sink()
        self._sleep = sleep_fn

    def _emit_trace(
        self,
        *,
        trace_name: str,
        model: str,
        success: bool,
        usage: AIUsage | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._trace_sink(
            AITraceEvent(
                trace_name=trace_name,
                model=model,
                usage=usage,
                success=success,
                error=error,
                metadata=metadata or {},
            )
        )

    def _post_generate_content(self, model: str, body: dict[str, Any]) -> httpx.Response:
        url = f"{GEMINI_API_BASE_URL}/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        if self._client is not None:
            return self._client.post(url, json=body, headers=headers)

        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(url, json=body, headers=headers)

    def _call_with_retries(
        self,
        *,
        model: str,
        body: dict[str, Any],
        trace_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, AIUsage]:
        if not self.api_key:
            err_msg = "GEMINI_API_KEY is not configured"
            self._emit_trace(
                trace_name=trace_name,
                model=model,
                success=False,
                error=err_msg,
                metadata=metadata,
            )
            raise GeminiAuthError(err_msg)

        started = time.perf_counter()
        last_error: GeminiClientError | None = None

        for attempt in range(self.max_retries):
            try:
                response = self._post_generate_content(model, body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = GeminiClientError(f"Gemini network error: {exc}")
                if attempt < self.max_retries - 1:
                    self._sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                self._emit_trace(
                    trace_name=trace_name,
                    model=model,
                    success=False,
                    error=str(last_error),
                    metadata=metadata,
                )
                raise last_error from exc

            if response.status_code in (401, 403):
                err_msg = f"Gemini authentication failed (HTTP {response.status_code})"
                self._emit_trace(
                    trace_name=trace_name,
                    model=model,
                    success=False,
                    error=err_msg,
                    metadata=metadata,
                )
                raise GeminiAuthError(err_msg)

            if response.status_code in RETRYABLE_STATUS_CODES:
                last_error = GeminiClientError(
                    f"Gemini temporary error (HTTP {response.status_code})"
                )
                if attempt < self.max_retries - 1:
                    self._sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                self._emit_trace(
                    trace_name=trace_name,
                    model=model,
                    success=False,
                    error=str(last_error),
                    metadata=metadata,
                )
                raise last_error

            if not response.is_success:
                err_msg = f"Gemini API error (HTTP {response.status_code})"
                self._emit_trace(
                    trace_name=trace_name,
                    model=model,
                    success=False,
                    error=err_msg,
                    metadata=metadata,
                )
                raise GeminiClientError(err_msg)

            latency_ms = (time.perf_counter() - started) * 1000
            try:
                payload = response.json()
                text = _extract_text(payload)
            except (ValueError, GeminiResponseFormatError) as exc:
                err_msg = f"Invalid Gemini response payload: {exc}"
                self._emit_trace(
                    trace_name=trace_name,
                    model=model,
                    success=False,
                    error=err_msg,
                    metadata=metadata,
                )
                raise GeminiResponseFormatError(err_msg) from exc

            usage = _extract_usage(payload, model=model, latency_ms=latency_ms)
            return text, usage

        assert last_error is not None
        raise last_error

    @staticmethod
    def _build_body(
        *,
        parts: list[dict[str, Any]],
        system_instruction: str | None,
        temperature: float,
        response_schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        generation_config: dict[str, Any] = {"temperature": temperature}
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseJsonSchema"] = response_schema.model_json_schema()

        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        return body

    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        trace_name: str = "generate_text",
        metadata: dict[str, Any] | None = None,
    ) -> AITextResponse:
        """Generate a plain-text response from Gemini."""
        target_model = model or self.default_model
        body = self._build_body(
            parts=[{"text": prompt}],
            system_instruction=system_instruction,
            temperature=temperature,
        )
        text, usage = self._call_with_retries(
            model=target_model,
            body=body,
            trace_name=trace_name,
            metadata=metadata,
        )
        self._emit_trace(
            trace_name=trace_name,
            model=target_model,
            success=True,
            usage=usage,
            metadata=metadata,
        )
        return AITextResponse(text=text, usage=usage)

    def generate_structured[T: BaseModel](
        self,
        prompt: str,
        response_schema: type[T],
        *,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        trace_name: str = "generate_structured",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[T, AIUsage]:
        """Request JSON conforming to a Pydantic schema and validate the result."""
        target_model = model or self.default_model
        body = self._build_body(
            parts=[{"text": prompt}],
            system_instruction=system_instruction,
            temperature=temperature,
            response_schema=response_schema,
        )
        raw_text, usage = self._call_with_retries(
            model=target_model,
            body=body,
            trace_name=trace_name,
            metadata=metadata,
        )
        return self._validate_structured_output(
            raw_text=raw_text,
            response_schema=response_schema,
            usage=usage,
            trace_name=trace_name,
            model=target_model,
            metadata=metadata,
        )

    def analyze_image[T: BaseModel](
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        response_schema: type[T],
        *,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        trace_name: str = "analyze_image",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[T, AIUsage]:
        """Analyze an image with Gemini multimodal vision and return a Pydantic model."""
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")
        clean_mime = mime_type.strip().lower()
        if not clean_mime.startswith("image/"):
            raise ValueError("mime_type must be a valid image MIME type")

        target_model = model or self.default_model
        encoded = base64.b64encode(image_bytes).decode("ascii")
        parts: list[dict[str, Any]] = [
            {"text": prompt},
            {"inlineData": {"mimeType": clean_mime, "data": encoded}},
        ]
        body = self._build_body(
            parts=parts,
            system_instruction=system_instruction,
            temperature=temperature,
            response_schema=response_schema,
        )
        raw_text, usage = self._call_with_retries(
            model=target_model,
            body=body,
            trace_name=trace_name,
            metadata=metadata,
        )
        return self._validate_structured_output(
            raw_text=raw_text,
            response_schema=response_schema,
            usage=usage,
            trace_name=trace_name,
            model=target_model,
            metadata=metadata,
        )

    def _validate_structured_output[T: BaseModel](
        self,
        *,
        raw_text: str,
        response_schema: type[T],
        usage: AIUsage,
        trace_name: str,
        model: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[T, AIUsage]:
        """Parse and validate structured JSON returned by Gemini."""
        cleaned = _strip_code_fences(raw_text)
        try:
            parsed = response_schema.model_validate_json(cleaned)
        except ValidationError as exc:
            err_msg = f"Gemini output failed schema validation: {exc}"
            self._emit_trace(
                trace_name=trace_name,
                model=model,
                success=False,
                usage=usage,
                error=err_msg,
                metadata=metadata,
            )
            raise GeminiResponseFormatError(err_msg) from exc

        self._emit_trace(
            trace_name=trace_name,
            model=model,
            success=True,
            usage=usage,
            metadata=metadata,
        )
        return parsed, usage
