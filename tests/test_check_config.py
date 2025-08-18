import logging
from bot import check_config


def test_check_config_only_logs_critical_missing(monkeypatch, caplog):
    monkeypatch.delenv("MEXC_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MEXC_SECRET_KEY", raising=False)
    monkeypatch.delenv("NOTIFY_URL", raising=False)
    with caplog.at_level(logging.INFO):
        check_config()
    messages = [r.getMessage() for r in caplog.records]
    assert any("MEXC_ACCESS_KEY" in m for m in messages)
    assert any("MEXC_SECRET_KEY" in m for m in messages)
    assert all("NOTIFY_URL" not in m for m in messages)
