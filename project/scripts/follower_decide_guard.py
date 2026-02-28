def is_valid_position(fr):
    """
    Autorise une décision uniquement si la position est réellement ouverte
    et suivie dans la FSM centrale.

    Conditions :
    - qty_ratio > 0  → exposition réelle (chemin nominal)
    - fallback: qty_open > 0 si qty_ratio reste à 0 à cause d'un drift de sync

    NOTE:
    - done_step n'indique PAS une clôture. C'est simplement le dernier step
      ack (open/partial/pyramide/close). Après une pyramide réussie,
      done_step vaut déjà 2.
    - Filtrer sur done_step == 0 bloquait toute nouvelle décision dès le
      premier ack, ce qui empêchait les enchaînements pyramide/partial/close.
    """
    def _f(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    qty_ratio = _f(fr["qty_ratio"])
    if qty_ratio > 0:
        return True

    qty_open = _f(fr["qty_open"])
    return qty_open > 0
