# -*- coding: utf-8 -*-
import os, time
from typing import Dict, Any, Optional, List
from .paths import resolve_paths, load_json, tail_lines, parse_signals_csv_lines, load_signals_any

def _stat(path: Optional[str]) -> Dict[str, Any]:
    if not path: 
        return {"exists": False, "reason": "chemin introuvable"}
    if not os.path.exists(path):
        return {"exists": False, "path": path, "reason": "fichier absent"}
    st = os.stat(path)
    return {
        "exists": True, "path": path, "size": st.st_size,
        "mtime": st.st_mtime, "age_s": max(0, int(time.time()-st.st_mtime))
    }

def diag_signals(limit_scan: int = 5000) -> Dict[str, Any]:
    p = resolve_paths()
    d = {"paths": p, "files": {}}
    # fichiers
    d["files"]["signals_csv"]  = _stat(p["signals_csv"])
    d["files"]["signals_json"] = _stat(p["signals_json"])
    # comptages / messages
    msgs: List[str] = []
    items = load_signals_any(limit_scan=limit_scan)
    d["count"] = len(items)

    if d["count"] == 0:
        if d["files"]["signals_csv"].get("exists"):
            # fichier présent mais peut-être vide ou colonnes inconnues
            lines = tail_lines(p["signals_csv"], 5)
            d["sample_csv_tail"] = lines
            if d["files"]["signals_csv"]["size"] == 0:
                msgs.append("signals.csv est présent mais vide (size=0).")
            elif not lines:
                msgs.append("signals.csv lisible mais aucune ligne décodable (encodage ?).")
            else:
                parsed = parse_signals_csv_lines(lines[-3:])
                if not parsed:
                    msgs.append("signals.csv ne contient pas les colonnes attendues (ts,symbol,tf,signal,details).")
        elif d["files"]["signals_json"].get("exists"):
            js = load_json(p["signals_json"]) or {}
            if isinstance(js, dict) and not js.get("items"):
                msgs.append("signals.json présent mais items=[] ou champs inattendus.")
            else:
                msgs.append("Aucun enregistrement utilisable dans signals.json.")
        else:
            msgs.append("Aucune source de signaux disponible (ni CSV, ni JSON).")
    else:
        # extrait pour debug
        d["first_item"] = items[0]

    d["messages"] = msgs
    d["ok"] = d["count"] > 0
    return d

def diag_history() -> Dict[str, Any]:
    p = resolve_paths()
    d = {"paths": p, "files": {}, "count": 0, "messages": []}
    d["files"]["history_json"] = _stat(p["history_json"])
    js = load_json(p["history_json"]) or {}
    items = js.get("items") if isinstance(js, dict) else (js if isinstance(js, list) else [])
    if isinstance(items, list):
        d["count"] = len(items)
        if d["count"] == 0:
            if d["files"]["history_json"].get("exists"):
                d["messages"].append("history.json présent mais items vide.")
            else:
                d["messages"].append("history.json introuvable.")
    else:
        d["messages"].append("history.json ne contient pas un tableau d'items.")
    d["ok"] = d["count"] > 0
    return d

def diag_heatmap() -> Dict[str, Any]:
    p = resolve_paths()
    d = {"paths": p, "files": {}, "count": 0, "messages": []}
    d["files"]["heatmap_json"] = _stat(p["heatmap_json"])
    js = load_json(p["heatmap_json"])
    if isinstance(js, dict) and "cells" in js:
        cells = js.get("cells") or []
        d["count"] = len(cells)
        if d["count"] == 0:
            d["messages"].append("heatmap.json présent mais cells vide.")
        d["source"] = "heatmap.json"
    else:
        d["messages"].append("heatmap.json indisponible → fallback sur signals.")
        from .paths import load_signals_any
        sigs = load_signals_any()
        d["fallback_signals"] = len(sigs)
        if len(sigs) == 0:
            d["messages"].append("aucun signal pour construire un fallback heatmap.")
        d["source"] = "fallback(signals)"
    d["ok"] = (d["count"] > 0) or ("fallback_signals" in d and d["fallback_signals"]>0)
    return d

def diag_stream() -> Dict[str, Any]:
    p = resolve_paths()
    d = {"paths": p, "files": {}, "messages": []}
    d["files"]["signals_csv"]  = _stat(p["signals_csv"])
    d["files"]["signals_json"] = _stat(p["signals_json"])
    if not d["files"]["signals_csv"].get("exists"):
        d["messages"].append("SSE lit en priorité signals.csv : fichier absent → seuls pings seront émis.")
    else:
        if d["files"]["signals_csv"]["size"] == 0:
            d["messages"].append("signals.csv présent mais vide → pas d'événements 'signal'.")
    d["ok"] = True  # SSE reste opérationnel même sans nouveaux events
    return d
