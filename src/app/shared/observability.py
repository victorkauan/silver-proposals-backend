import logging
import os
import re
import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.aws import AwsXRayPropagator
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
# Load balancer and container health checks would flood the logs and traces.
_QUIET_PATHS = {"/health", "/ready"}
_SHARE_TOKEN_IN_PATH = re.compile(r"(/public/proposals/)[^/?#]+")
_URL_ATTRIBUTES = ("http.url", "http.target", "url.full", "url.path")

logger = logging.getLogger("app.request")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id and not hasattr(record, "request_id"):
            record.request_id = request_id
        context = trace.get_current_span().get_span_context()
        if context.is_valid and not hasattr(record, "trace_id"):
            trace_id = f"{context.trace_id:032x}"
            record.trace_id = f"1-{trace_id[:8]}-{trace_id[8:]}"
        return True


# One log line per request, with the route template: the raw path may hold share tokens.
class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.encode(), b"").decode()
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        logged = False

        def log() -> None:
            nonlocal logged
            if logged or scope.get("path") in _QUIET_PATHS:
                return
            logged = True
            route = getattr(scope.get("route"), "path", "unmatched")
            fields: dict[str, Any] = {
                "method": scope.get("method"),
                "route": route,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
            logger.log(
                logging.ERROR if status >= 500 else logging.INFO, "request_completed", extra=fields
            )

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [
                    *message["headers"],
                    (REQUEST_ID_HEADER.encode(), request_id.encode()),
                ]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                log()

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            log()
            request_id_var.reset(token)


# Span URLs are exported to X-Ray as-is, and the share token is part of the path.
def _redact_share_token(span: trace.Span, scope: dict[str, Any]) -> None:
    attributes = getattr(span, "attributes", None) or {}
    for key in _URL_ATTRIBUTES:
        value = attributes.get(key)
        if isinstance(value, str):
            span.set_attribute(key, _SHARE_TOKEN_IN_PATH.sub(r"\1{token}", value))


# Tracing is on only with an OTLP endpoint (the collector sidecar); local runs and tests stay quiet.
def setup_tracing(app: FastAPI, environment: str, exporter: SpanExporter | None = None) -> bool:
    if exporter is None:
        if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            return False
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter()

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "silver-proposals-api"),
            "deployment.environment": environment,
        }
    )
    provider = TracerProvider(resource=resource, id_generator=AwsXRayIdGenerator())
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    set_global_textmap(AwsXRayPropagator())

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,ready",
        tracer_provider=provider,
        server_request_hook=_redact_share_token,
    )
    BotocoreInstrumentor().instrument(tracer_provider=provider)  # type: ignore[no-untyped-call]
    SQLAlchemyInstrumentor().instrument(tracer_provider=provider)
    return True
