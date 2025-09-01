# engine/strategy_loader.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, TypedDict, Literal
import json

RiskProfile = Literal["conservateur", "modéré", "agressif"]

class RiskEntry(TypedDict):
    min_score_buy: float
    min_score_sell: float
    risk_per_trade_pct: float  # 0.005 = 0.5%
    max_leverage: float

def load_strategy(path: Path) -> Dict:
    """
    Charge config/strategy.json et prépare:
    - thresholds buy/sell
    - defaults SL/TP
    - risk_by_profile: mapping RiskProfile -> RiskEntry
    """
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Seuils globaux (outputs)
    buy_th = float(cfg["outputs"]["signals"]["buy_threshold"])
    sell_th = float(cfg["outputs"]["signals"]["sell_threshold"])

    # Base risk depuis risk_management
    base_risk_pct = float(cfg["risk_management"]["position_sizing"]["risk_pct_per_trade"])  # ex: 0.005
    base_max_lev = float(cfg["risk_management"]["position_sizing"]["max_leverage"])         # ex: 3.0

    # Multiplicateurs par profil
    prof_mult = {
        "conservateur": {"risk_pct": 0.5, "lev": 0.5, "th_add": +0.05},
        "modéré":       {"risk_pct": 1.0, "lev": 1.0, "th_add":  0.00},
        "agressif":     {"risk_pct": 2.0, "lev": 1.5, "th_add": -0.05},
    }

    risk_by_profile: Dict[RiskProfile, RiskEntry] = {}
    for p, m in prof_mult.items():
        risk_by_profile[p] = {
            "min_score_buy":  max(0.0, min(1.0, buy_th  + m["th_add"])),
            "min_score_sell": max(0.0, min(1.0, sell_th + m["th_add"])),
            "risk_per_trade_pct": base_risk_pct * m["risk_pct"],
            "max_leverage": base_max_lev * m["lev"],
        }

    # Valeurs par défaut SL/TP
    entry_defaults = {
        "sl_atr_mult": 1.2,
        "tp_r_multiple": [2.0, 3.0],
    }

    return {
        "strategy_name": cfg["strategy_name"],
        "risk_by_profile": risk_by_profile,
        "entry_defaults": entry_defaults,
        "costs": cfg["costs"],
        "raw": cfg,
    }
