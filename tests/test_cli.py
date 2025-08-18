"""Tests for the command line interface defined in :mod:`cli`."""

from __future__ import annotations

import cli


def test_opt_invokes_parallel_optimization(monkeypatch):
    """The ``opt`` command should call ``run_parallel_optimization``."""

    called = {}

    def fake_run(pairs, tf, jobs):  # pragma: no cover - executed via CLI
        called["args"] = (pairs, tf, jobs)

    monkeypatch.setattr(cli, "run_parallel_optimization", fake_run)
    cli.main(["opt", "--pairs", "BTCUSDT", "ETHUSDT", "--tf", "1h", "--jobs", "4"])
    assert called["args"] == (["BTCUSDT", "ETHUSDT"], "1h", 4)


def test_walkforward_invokes_analysis(monkeypatch):
    """The ``walkforward`` command calls ``run_walkforward_analysis``."""

    called = {}

    def fake_run(pair, tf, splits, train_ratio):  # pragma: no cover
        called["args"] = (pair, tf, splits, train_ratio)

    monkeypatch.setattr(cli, "run_walkforward_analysis", fake_run)
    cli.main(
        [
            "walkforward",
            "--pair",
            "BTCUSDT",
            "--tf",
            "1m",
            "--splits",
            "3",
            "--train-ratio",
            "0.8",
        ]
    )
    assert called["args"] == ("BTCUSDT", "1m", 3, 0.8)


def test_live_invokes_async_pipeline(monkeypatch):
    """The ``live`` command must execute the async pipeline via ``asyncio.run``."""

    called = {}

    async def fake_live(pairs, tfs):  # pragma: no cover - executed asynchronously
        called["args"] = (pairs, list(tfs))

    monkeypatch.setattr(cli, "run_live_pipeline", fake_live)
    cli.main(["live", "--pairs", "BTCUSDT", "ETHUSDT", "--tfs", "1m", "1h"])
    assert called["args"] == (["BTCUSDT", "ETHUSDT"], ["1m", "1h"])


def test_bump_version_invokes_helper(monkeypatch):
    """The ``bump-version`` command calls ``bump_version_from_git``."""

    called = {}

    def fake_bump():  # pragma: no cover - executed via CLI
        called["called"] = True
        return "0.1.0"

    monkeypatch.setattr(cli, "bump_version_from_git", fake_bump)
    cli.main(["bump-version"])
    assert called["called"] is True

