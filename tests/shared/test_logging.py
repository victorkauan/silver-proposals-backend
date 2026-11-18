import json
import logging

from app.shared.logging import JsonFormatter


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"name": "app.test", "levelname": "INFO", "msg": "generation_completed", "latency_ms": 42}
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "generation_completed"
    assert payload["latency_ms"] == 42
    assert payload["logger"] == "app.test"
