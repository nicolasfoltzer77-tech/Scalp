from pathlib import Path
import json

def test_health_ok():
    p = Path("docs/health.json")
    j = json.loads(p.read_text())
    assert j.get("status") == "ok"
    assert "generated_at" in j

def test_index_not_empty():
    p = Path("docs/index.html")
    assert p.exists() and p.stat().st_size > 100
