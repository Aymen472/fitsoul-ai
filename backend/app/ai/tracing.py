"""AI observability models, structured logging, and optional Langfuse trace sink."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger("fitsoul.ai")


class AIUsage(BaseModel):
    """Token counts, estimated USD cost, and latency for a single AI call."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0


class AITraceEvent(BaseModel):
    """Observability event emitted after each AI invocation."""

    trace_name: str
    model: str
    usage: AIUsage | None = None
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


TraceSink = Callable[[AITraceEvent], None]


def log_trace_event(event: AITraceEvent) -> None:
    """Log AI call usage and status without recording sensitive prompts or secrets."""
    tokens = event.usage.total_tokens if event.usage is not None else 0
    cost_usd = event.usage.estimated_cost_usd if event.usage is not None else 0.0
    latency_ms = event.usage.latency_ms if event.usage is not None else 0.0

    if event.success:
        logger.info(
            "ai_trace name=%s model=%s success=true tokens=%d cost_usd=%.6f latency_ms=%.1f",
            event.trace_name,
            event.model,
            tokens,
            cost_usd,
            latency_ms,
        )
    else:
        logger.warning(
            "ai_trace name=%s model=%s success=false tokens=%d cost_usd=%.6f "
            "latency_ms=%.1f error=%s",
            event.trace_name,
            event.model,
            tokens,
            cost_usd,
            latency_ms,
            event.error or "unknown",
        )


class LangfuseTraceSink:
    """Lightweight HTTP sink sending AI trace events to Langfuse ingestion API."""

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "https://cloud.langfuse.com",
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    def _build_payload(self, event: AITraceEvent) -> dict[str, Any]:
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        trace_id = str(uuid4())
        gen_id = str(uuid4())

        generation_body: dict[str, Any] = {
            "id": gen_id,
            "traceId": trace_id,
            "name": event.trace_name,
            "model": event.model,
            "startTime": now_iso,
            "endTime": now_iso,
            "level": "DEFAULT" if event.success else "ERROR",
            "statusMessage": event.error,
            "metadata": event.metadata,
        }
        if event.usage is not None:
            generation_body["usage"] = {
                "input": event.usage.prompt_tokens,
                "output": event.usage.completion_tokens,
                "total": event.usage.total_tokens,
            }

        return {
            "batch": [
                {
                    "id": str(uuid4()),
                    "timestamp": now_iso,
                    "type": "trace-create",
                    "body": {
                        "id": trace_id,
                        "name": event.trace_name,
                        "metadata": event.metadata,
                    },
                },
                {
                    "id": str(uuid4()),
                    "timestamp": now_iso,
                    "type": "generation-create",
                    "body": generation_body,
                },
            ]
        }

    def __call__(self, event: AITraceEvent) -> None:
        """Log locally and best-effort forward the trace event to Langfuse."""
        log_trace_event(event)
        url = f"{self.host}/api/public/ingestion"
        payload = self._build_payload(event)
        auth = (self.public_key, self.secret_key)

        try:
            if self._client is not None:
                response = self._client.post(url, json=payload, auth=auth)
                response.raise_for_status()
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, json=payload, auth=auth)
                    response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Langfuse ingestion failed: %s", exc)


def build_default_trace_sink() -> TraceSink:
    """Return a Langfuse sink when configured, otherwise standard Python logging."""
    settings = get_settings()
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        return LangfuseTraceSink(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return log_trace_event
