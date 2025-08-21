import json
from pathlib import Path
from typing import Any, Dict

import pytest

import bitget_futures_pairs as bfp


class DummyResponse:
    def __init__(self, status: int, payload: Dict[str, Any]):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_fetch_contracts_success(monkeypatch):
    payload = {"code": "00000", "data": [{"symbol": "BTCUSDT"}]}

    def fake_get(url, params=None, timeout=0):
        return DummyResponse(200, payload)

    monkeypatch.setattr(bfp, "requests", type("R", (), {"get": staticmethod(fake_get)})())
    contracts = bfp.fetch_contracts("USDT-FUTURES")
    assert contracts == payload["data"]


def test_fetch_contracts_error(monkeypatch):
    payload = {"code": "10001"}

    def fake_get(url, params=None, timeout=0):
        return DummyResponse(200, payload)

    monkeypatch.setattr(bfp, "requests", type("R", (), {"get": staticmethod(fake_get)})())
    with pytest.raises(RuntimeError):
        bfp.fetch_contracts("USDT-FUTURES")


def test_normalize_rows():
    contracts = [
        {
            "symbol": "BTCUSDT",
            "baseCoin": "BTC",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
            "maxLever": "50",
            "minLever": "1",
            "minTradeNum": "0.001",
            "sizeMultiplier": "1",
            "pricePlace": "2",
            "volumePlace": "3",
            "launchTime": 0,
            "deliveryTime": 0,
        }
    ]
    rows = bfp.normalize_rows("USDT-FUTURES", contracts)
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["productType"] == "USDT-FUTURES"


def test_write_csv(tmp_path: Path):
    path = tmp_path / "pairs.csv"
    bfp.write_csv([], str(path))
    assert path.exists()
    content = path.read_text().splitlines()
    assert content[0].startswith("productType,")
