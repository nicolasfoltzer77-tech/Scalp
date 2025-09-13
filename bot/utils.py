import json
import os
from datetime import datetime

DATA_DIR = "/opt/scalp/data"

def load_json(filename, default=None):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def short_time():
    return datetime.now().strftime("%H%M")

def format_table(headers, rows):
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    out = []
    out.append(" | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers)))
    out.append("-+-".join("-" * w for w in col_widths))
    for row in rows:
        out.append(" | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    return "\n".join(out)
