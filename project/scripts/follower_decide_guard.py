def is_valid_position(fr):
    """
    Autorise une décision uniquement si la position est réellement ouverte
    et suivie dans la FSM centrale.

    Conditions :
    - qty_ratio > 0  → exposition réelle
    - done_step == 0 → pas déjà clôturée
    """
    return (
        fr["qty_ratio"] is not None
        and fr["qty_ratio"] > 0
        and fr["done_step"] == 0
    )

