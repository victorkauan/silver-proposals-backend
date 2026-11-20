import asyncio

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.shared.config import get_settings


def test_purge_loop_keeps_running_after_a_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[int] = []

    def flaky() -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database unavailable")
        raise asyncio.CancelledError

    monkeypatch.setattr(main, "purge_once", flaky)

    async def run() -> None:
        with pytest.raises(asyncio.CancelledError):
            await main.purge_periodically(0)

    asyncio.run(run())

    assert len(calls) == 2
    assert "refresh_token_purge_failed" in caplog.text


def test_lifespan_starts_and_stops_the_purge_task(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()

    async def fake_loop(interval: int) -> None:
        assert interval == 5
        started.set()
        await asyncio.sleep(3600)

    monkeypatch.setenv("TOKEN_PURGE_INTERVAL_MINUTES", "5")
    get_settings.cache_clear()
    monkeypatch.setattr(main, "purge_periodically", fake_loop)
    try:
        with TestClient(main.create_app()) as client:
            assert client.get("/health").status_code == 200
        assert started.is_set()
    finally:
        get_settings.cache_clear()
