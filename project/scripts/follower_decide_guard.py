def is_valid_position(fr):
    """
    Autorise une décision uniquement si la position est réellement ouverte
    et suivie dans la FSM centrale.

    Conditions :
    - qty_ratio > 0  → exposition réelle

    NOTE:
    - done_step n'indique PAS une clôture. C'est simplement le dernier step
      ack (open/partial/pyramide/close). Après une pyramide réussie,
      done_step vaut déjà 2.
    - Filtrer sur done_step == 0 bloquait toute nouvelle décision dès le
      premier ack, ce qui empêchait les enchaînements pyramide/partial/close.
    """
    return (
        fr["qty_ratio"] is not None
        and fr["qty_ratio"] > 0
    )
