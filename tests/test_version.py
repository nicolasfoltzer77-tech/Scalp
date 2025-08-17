import pytest
from scalp import version


def test_get_version(monkeypatch, tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("1.2.3")
    monkeypatch.setattr(version, "_VERSION_FILE", vfile)
    assert version.get_version() == "1.2.3"


def test_bump_version(monkeypatch, tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("0.1.2\n")
    monkeypatch.setattr(version, "_VERSION_FILE", vfile)
    assert version.bump_version("minor") == "0.2.0"
    assert vfile.read_text().strip() == "0.2.0"


def test_bump_version_invalid_part(monkeypatch, tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("0.1.0\n")
    monkeypatch.setattr(version, "_VERSION_FILE", vfile)
    with pytest.raises(ValueError):
        version.bump_version("foo")


def test_bump_from_message(monkeypatch, tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("1.0.0\n")
    monkeypatch.setattr(version, "_VERSION_FILE", vfile)
    assert version.bump_version_from_message("feat: add x") == "1.1.0"
    assert version.bump_version_from_message("fix: bug") == "1.1.1"
    assert version.bump_version_from_message("feat!: major change") == "2.0.0"
