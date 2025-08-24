from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description="Promouvoir stratégies validées")
    ap.add_argument("--draft", required=True, help=".../strategies.yml.next (JSON lisible)")
    ap.add_argument("--target", default="engine/config/strategies.yml")
    args = ap.parse_args()

    draft = Path(args.draft); target = Path(args.target)
    if not draft.exists():
        print(f"[!] Draft introuvable: {draft}"); return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.with_suffix(".yml.bak").write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[✓] Stratégies promues -> {target}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())