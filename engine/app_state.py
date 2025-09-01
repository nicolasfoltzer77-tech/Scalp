# engine/app_state.py
from __future__ import annotations
from pathlib import Path
from typing import Literal, Dict
import json

RiskProfile = Literal["conservateur","modéré","agressif"]
Mode = Literal["paper","real"]

DEFAULT = {"mode": "paper", "risk_level": 2}

class AppState:
    """
    État global contrôlé par l'API/Dashboard :
      - mode: paper / real
      - risk_level: 1..3 -> profil (conservateur/modéré/agressif)
    Persisté dans config/state.json
    """
    def __init__(self, path: Path = Path("config/state.json")):
        self.path = path
        self._state = DEFAULT.copy()
        if path.exists():
            try:
                self._state.update(json.loads(path.read_text("utf-8")))
            except Exception:
                pass

    @property
    def mode(self) -> Mode:
        return "real" if self._state.get("mode") == "real" else "paper"

    @property
    def risk_level(self) -> int:
        rl = int(self._state.get("risk_level", 2))
        return 1 if rl <= 1 else 3 if rl >= 3 else 2

    @property
    def risk_profile(self) -> RiskProfile:
        return {1: "conservateur", 2: "modéré", 3: "agressif"}[self.risk_level]

    def as_dict(self) -> Dict:
        return {"mode": self.mode, "risk_level": self.risk_level, "risk_profile": self.risk_profile}

    def update(self, **fields) -> Dict:
        if "mode" in fields:
            self._state["mode"] = "real" if fields["mode"] == "real" else "paper"
        if "risk_level" in fields:
            rl = int(fields["risk_level"])
            self._state["risk_level"] = 1 if rl <= 1 else 3 if rl >= 3 else 2
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), "utf-8")
        return self.as_dict()
