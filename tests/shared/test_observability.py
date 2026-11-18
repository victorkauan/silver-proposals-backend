import json
import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.shared.logging import JsonFormatter
from app.shared.observability import RequestContextFilter, RequestLogMiddleware, setup_tracing


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/public/proposals/{token}")
    def public(token: str) -> dict[str, str]:
        return {"token": token}

    @app.get("/boom")
    def boom() -> None:
        raise HTTPException(status_code=503)

    @app.get("/stream")
    def stream() -> object:
        from fastapi.responses import StreamingResponse

        return StreamingResponse(iter([b"a", b"b"]), media_type="text/event-stream")

    app.add_middleware(RequestLogMiddleware)
    return app


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def records() -> Iterator[Capture]:
    # The app logger does not propagate to the root logger (see configure_logging), so pytest's
    # caplog cannot see it once the app is imported; capture the request logger directly.
    capture = Capture()
    request_logger = logging.getLogger("app.request")
    request_logger.addHandler(capture)
    try:
        yield capture
    finally:
        request_logger.removeHandler(capture)


def request_logs(capture: Capture) -> list[logging.LogRecord]:
    return [r for r in capture.records if r.name == "app.request"]


def test_logs_the_route_template_and_never_the_raw_path(records: Capture) -> None:
    response = TestClient(build_app()).get("/public/proposals/secret-token-value")

    assert response.status_code == 200
    [record] = request_logs(records)
    assert record.getMessage() == "request_completed"
    assert record.__dict__["route"] == "/public/proposals/{token}"
    assert record.__dict__["status"] == 200
    assert record.__dict__["method"] == "GET"
    assert record.__dict__["duration_ms"] >= 0
    assert "secret-token-value" not in json.dumps(record.__dict__, default=str)


def test_returns_and_reuses_a_valid_request_id(records: Capture) -> None:
    client = TestClient(build_app())

    generated = client.get("/public/proposals/x").headers["x-request-id"]
    reused = client.get("/public/proposals/x", headers={"X-Request-ID": "client-req-1234"})
    rejected = client.get("/public/proposals/x", headers={"X-Request-ID": "bad id!"})

    assert len(generated) == 32
    assert reused.headers["x-request-id"] == "client-req-1234"
    assert rejected.headers["x-request-id"] != "bad id!"


def test_server_errors_are_logged_as_errors(records: Capture) -> None:
    TestClient(build_app()).get("/boom")

    [record] = request_logs(records)
    assert record.levelno == logging.ERROR
    assert record.__dict__["status"] == 503


def test_streaming_responses_are_logged_once_after_the_body(
    records: Capture,
) -> None:
    response = TestClient(build_app()).get("/stream")

    assert response.text == "ab"
    assert len(request_logs(records)) == 1


def test_health_checks_are_not_logged(records: Capture) -> None:
    TestClient(build_app()).get("/health")

    assert request_logs(records) == []


def test_log_lines_carry_the_request_id() -> None:
    from app.shared.observability import request_id_var

    record = logging.makeLogRecord({"msg": "inside"})
    token = request_id_var.set("req-abcdefgh")
    try:
        RequestContextFilter().filter(record)
    finally:
        request_id_var.reset(token)

    assert json.loads(JsonFormatter().format(record))["request_id"] == "req-abcdefgh"


def test_tracing_is_off_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert setup_tracing(FastAPI(), "local") is False


def test_tracing_exports_request_spans_with_xray_ids() -> None:
    exporter = InMemorySpanExporter()
    app = build_app()

    assert setup_tracing(app, "staging", exporter=exporter) is True
    TestClient(app).get("/public/proposals/abc")
    from opentelemetry import trace

    trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]

    spans = exporter.get_finished_spans()
    server = [s for s in spans if s.kind.name == "SERVER"]
    assert server, [s.name for s in spans]
    assert server[0].attributes is not None
    assert server[0].attributes.get("http.route") == "/public/proposals/{token}"
    assert server[0].resource.attributes["deployment.environment"] == "staging"
    # X-Ray trace IDs start with the epoch seconds of the trace.
    assert f"{server[0].context.trace_id:032x}"[:8] != "00000000"
