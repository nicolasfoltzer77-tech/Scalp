# ... (tout le fichier identique à ma version précédente)
# Remplacement intégral de la fonction load_combined_or_split :

def load_combined_or_split(schema_json: Optional[str],
                           schema_backtest_json: Optional[str],
                           schema_entries_json: Optional[str]) -> Tuple[Dict, Dict]:
    """
    Renvoie (schema_backtest, schema_entries)
    Priorité :
      1) schema_json (JSON unique)
      2) schema_backtest_json + schema_entries_json
      3) defaults: <repo_root>/schemas/schema_backtest.json + schema_entries.json
    """
    import os, json
    if schema_json:
        with open(schema_json, "r", encoding="utf-8") as f:
            full = json.load(f)
        back = {
            "schema_version": full.get("schema_version", ""),
            "strategy_name": full.get("strategy_name", "TwoLayer_Scalp"),
            "assets": full.get("assets", []),
            "timeframes": full.get("timeframes", {}),
            "regime_layer": full.get("regime_layer", {}),
            "risk_management": full.get("risk_management", {}),
            "costs": full.get("costs", {}),
            "backtest": full.get("backtest", {}),
            "optimization": full.get("optimization", {}),
            "outputs": full.get("outputs", {})
        }
        entries = {"entry_layer": full.get("entry_layer", {}), "execution": full.get("execution", {})}
        return back, entries

    if schema_backtest_json and schema_entries_json:
        with open(schema_backtest_json, "r", encoding="utf-8") as f:
            back = json.load(f)
        with open(schema_entries_json, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return back, entries

    # --- Fallback défaut: dossiers schemas/ à la racine du repo ---
    here = os.path.abspath(os.path.dirname(__file__))             # .../engine/strategies
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))   # racine repo
    sb_def = os.path.join(repo_root, "schemas", "schema_backtest.json")
    se_def = os.path.join(repo_root, "schemas", "schema_entries.json")
    if os.path.isfile(sb_def) and os.path.isfile(se_def):
        with open(sb_def, "r", encoding="utf-8") as f:
            back = json.load(f)
        with open(se_def, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return back, entries

    raise FileNotFoundError(
        "Aucun schéma fourni et fichiers par défaut introuvables. "
        "Place `schemas/schema_backtest.json` et `schemas/schema_entries.json` à la racine, "
        "ou passe --schema-json / --schema-backtest + --schema-entries."
    )