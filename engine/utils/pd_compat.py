# /opt/scalp/engine/utils/pd_compat.py
"""
Compatibilité Pandas 2.x : réintroduit DataFrame.append()
en le redirigeant vers pd.concat, pour éviter de modifier
tous les appels historiques du projet.
"""
from __future__ import annotations

def patch_pandas_append() -> None:
    import pandas as pd  # import local pour ne pas imposer pandas à l'import module
    if hasattr(pd.DataFrame, "append"):
        return  # déjà présent (pandas < 2.0) ou déjà patché

    def _append(self, other, ignore_index: bool = False, **kwargs):
        """
        Emule DataFrame.append(other, ignore_index=...) via pd.concat.
        Accepte autres types usuels (Series, dict, list/tuple d'une ligne).
        """
        import pandas as pd

        if isinstance(other, pd.Series):
            other = other.to_frame().T
        elif isinstance(other, dict):
            other = pd.DataFrame([other])
        elif isinstance(other, (list, tuple)):
            # On tente d'aligner sur les colonnes existantes si possible
            other = pd.DataFrame([other], columns=list(self.columns)[:len(other)])
        elif isinstance(other, pd.DataFrame):
            pass
        else:
            # Dernier recours : on enveloppe dans un DataFrame une-ligne
            other = pd.DataFrame([other])

        return pd.concat([self, other], ignore_index=ignore_index)

    # monkey-patch
    setattr(pd.DataFrame, "append", _append)
