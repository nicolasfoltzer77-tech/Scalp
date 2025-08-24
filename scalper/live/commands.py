# scalper/live/commands.py
from __future__ import annotations
from typing import Any, AsyncIterator, Dict

async def command_stream() -> AsyncIterator[Dict[str, Any]]:
    # Exemple: brancher une vraie source d’événements/commandes ici si besoin.
    while False:
        yield {}