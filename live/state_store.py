# live/state_store.py
from __future__ import annotations
import json, os, time, asyncio
from typing import Callable, Dict, Any

class StateStore:
    """
    Persistance légère de l'état (FSM + horodatages) dans un JSON.
    - save_state(snapshot: dict) -> écrit sur disque
    - load_state() -> dict
    - task_autosave(get_snapshot: callable) -> boucle d’auto‑save
    """

    def __init__(self, filepath: str, period_s: float = 10.0) -> None:
        self.filepath = filepath
        self.period_s = period_s
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self._running = False

    # -------- I/O --------
    def save_state(self, snapshot: Dict[str, Any]) -> None:
        tmp = self.filepath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.filepath)

    def load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    # -------- Autosave --------
    async def task_autosave(self, get_snapshot: Callable[[], Dict[str, Any]]):
        self._running = True
        while self._running:
            try:
                snap = get_snapshot()
                snap["saved_at"] = int(time.time() * 1000)
                self.save_state(snap)
            except Exception:
                pass
            await asyncio.sleep(self.period_s)

    def stop(self): self._running = False