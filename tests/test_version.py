import pytest
from scalp import version


def test_get_version(monkeypatch, tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("1.2.3")
    monkeypatch.setattr(version, "_VERSION_FILE", vfile)
    assert version.get_version() == "1.2.3"


def test_bump_version(monkeypatch, tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("0.1.2")
    monkeypatch.setattr(version, "_VERSION_FILE", vfile)
    assert version.bump_version("minor") == "0.2.0"
    assert vfile.read_text() == "0.2.0"
