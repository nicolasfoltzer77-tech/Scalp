import logging
from bot import check_config


def test_check_config_only_logs_critical_missing(monkeypatch, caplog):
    monkeypatch.delenv("BITGET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("BITGET_SECRET_KEY", raising=False)
    monkeypatch.delenv("NOTIFY_URL", raising=False)
    with caplog.at_level(logging.INFO):
        check_config()
    messages = [r.getMessage() for r in caplog.records]
    assert any("BITGET_ACCESS_KEY" in m for m in messages)
    assert any("BITGET_SECRET_KEY" in m for m in messages)
    assert all("NOTIFY_URL" not in m for m in messages)


def test_check_config_does_not_log_present_keys(monkeypatch, caplog):
    monkeypatch.setenv("BITGET_ACCESS_KEY", "abcdef")
    monkeypatch.setenv("BITGET_SECRET_KEY", "abcdef")
    monkeypatch.setenv("BITGET_PASSPHRASE", "abcdef")
    with caplog.at_level(logging.INFO):
        check_config()
    assert caplog.records == []
