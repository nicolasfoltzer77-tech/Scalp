# scalp/live/notify.py
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Optional, List, Union

# ---------------------------------------------------------------------
# Config & utilitaires
# ---------------------------------------------------------------------

QUIET = int(os.getenv("QUIET", "0") or "0")

def _log(msg: str) -> None:
    if not QUIET:
        print(f"[notify] {msg}", flush=True)

# ---------------------------------------------------------------------
# Modèle de message de commande (transport-agnostic)
# ---------------------------------------------------------------------

@dataclass
class CommandMessage:
    text: str
    chat_id: Optional[int] = None
    user: Optional[str] = None
    ts: Optional[int] = None  # epoch ms

# ---------------------------------------------------------------------
# Interface Notifier
# ---------------------------------------------------------------------

class Notifier:
    """Interface de notification + menus (fallback texte)."""

    async def start(self) -> None:  # pragma: no cover (interface)
        raise NotImplementedError

    async def stop(self) -> None:  # pragma: no cover (interface)
        raise NotImplementedError

    async def send(self, text: str) -> None:  # pragma: no cover (interface)
        raise NotImplementedError

    async def send_menu(self, text: str, options: List[str]) -> None:
        """
        Envoie un menu. Fallback: simple liste numérotée.
        Si ton backend Telegram gère un clavier, surcharge dans TelegramNotifier.
        """
        opts = "\n".join(f"{i+1}) {o}" for i, o in enumerate(options))
        await self.send(f"{text}\n{opts}\nRéponds par le numéro ou la valeur exacte.")

# ---------------------------------------------------------------------
# NullNotifier (no-op)
# ---------------------------------------------------------------------

class NullNotifier(Notifier):
    def __init__(self) -> None:
        self._started = False

    async def start(self) -> None:
        self._started = True
        _log("NullNotifier started")

    async def stop(self) -> None:
        self._started = False
        _log("NullNotifier stopped")

    async def send(self, text: str) -> None:
        _log(f"NULL >> {text}")

# ---------------------------------------------------------------------
# CommandStream (basé sur une queue alimentée par le backend)
# ---------------------------------------------------------------------

class CommandStream:
    """
    Flux asynchrone de CommandMessage. Le backend (TelegramNotifier) y pousse
    les messages reçus, on les consomme via: `async for msg in stream: ...`
    """

    def __init__(self, allowed_chat_id: Optional[int] = None) -> None:
        self._q: asyncio.Queue[CommandMessage] = asyncio.Queue()
        self._allowed_chat_id = allowed_chat_id
        self._closed = False

    def push(self, msg: CommandMessage) -> None:
        # Filtre optionnel par chat_id
        if self._allowed_chat_id is not None and msg.chat_id is not None:
            if msg.chat_id != self._allowed_chat_id:
                return
        # Normalise le texte
        msg.text = (msg.text or "").strip()
        if msg.text == "":
            return
        self._q.put_nowait(msg)

    async def close(self) -> None:
        self._closed = True
        # Injecte un message spécial pour débloquer les consommateurs
        await self._q.put(CommandMessage(text="__STREAM_CLOSED__"))

    def __aiter__(self) -> AsyncIterator[Union[str, CommandMessage]]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[Union[str, CommandMessage]]:
        while not self._closed:
            msg = await self._q.get()
            if msg.text == "__STREAM_CLOSED__":
                break
            # Par compatibilité: retourner .text (chaîne) si le consommateur ne veut que le texte
            yield msg.text if isinstance(msg, CommandMessage) else msg

# ---------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------

class TelegramNotifier(Notifier):
    """
    Notifier Telegram découplé.
    - Utilise une implémentation 'TelegramAsync' fournie par ton projet.
    - Construit un CommandStream et y pousse les messages entrants.
    - Filtre par TELEGRAM_CHAT_ID si fourni.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[int] = None,
        telegram_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        """
        Args:
            token: BOT token (env TELEGRAM_BOT_TOKEN si None)
            chat_id: chat id cible (env TELEGRAM_CHAT_ID si None). Si fourni, filtre les commandes entrantes.
            telegram_factory: callable retournant une instance compatible avec:
                - await tg.start()
                - await tg.stop()
                - await tg.send_message(text, chat_id=...)
                - tg.set_message_handler(callback)  # callback(chat_id:int, user:str|None, text:str, ts_ms:int)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        env_chat = os.getenv("TELEGRAM_CHAT_ID")
        self.chat_id = chat_id if chat_id is not None else (int(env_chat) if env_chat else None)
        self.telegram_factory = telegram_factory or _default_telegram_factory

        if not self.token:
            raise RuntimeError("TelegramNotifier: TELEGRAM_BOT_TOKEN manquant")

        self._tg = None  # type: ignore
        self._started = False
        self._stream = CommandStream(allowed_chat_id=self.chat_id)

    @property
    def command_stream(self) -> CommandStream:
        return self._stream

    async def start(self) -> None:
        if self._started:
            return
        self._tg = self.telegram_factory(self.token)
        if not hasattr(self._tg, "set_message_handler"):
            raise RuntimeError("Telegram backend invalide: set_message_handler manquant")

        # Enregistre le callback pour alimenter le CommandStream
        def _on_message(chat_id: int, user: Optional[str], text: str, ts_ms: int) -> None:
            self._stream.push(CommandMessage(text=text, chat_id=chat_id, user=user, ts=ts_ms))

        self._tg.set_message_handler(_on_message)
        await self._tg.start()
        self._started = True
        _log("TelegramNotifier started")

        # Message d’accueil
        try:
            await self.send("🤖 Bot prêt. Commandes: /setup /status /pause /resume /stop")
        except Exception:
            pass

    async def stop(self) -> None:
        if not self._started:
            return
        try:
            await self._stream.close()
        except Exception:
            pass
        try:
            if self._tg:
                await self._tg.stop()
        finally:
            self._started = False
            _log("TelegramNotifier stopped")

    async def send(self, text: str) -> None:
        if not self._started or not self._tg:
            raise RuntimeError("TelegramNotifier non démarré")
        # Si chat_id paramétré, on cible; sinon le backend peut avoir un défaut (ex: dernier chat)
        await self._tg.send_message(text, chat_id=self.chat_id)

    async def send_menu(self, text: str, options: List[str]) -> None:
        """
        Essaie d’envoyer un clavier; sinon fallback numéroté.
        On considère que le backend peut offrir send_message(..., reply_markup=...)
        """
        if not self._started or not self._tg:
            raise RuntimeError("TelegramNotifier non démarré")

        keyboard_supported = hasattr(self._tg, "send_message")
        reply_markup = None
        # Tentative de clavier simple si le backend l'accepte (liste verticale)
        try:
            reply_markup = {"keyboard": [[o] for o in options], "resize_keyboard": True, "one_time_keyboard": True}
            await self._tg.send_message(text, chat_id=self.chat_id, reply_markup=reply_markup)
        except Exception:
            # Fallback texte
            opts = "\n".join(f"{i+1}) {o}" for i, o in enumerate(options))
            await self._tg.send_message(f"{text}\n{opts}\nRéponds par le numéro ou la valeur exacte.", chat_id=self.chat_id)

# ---------------------------------------------------------------------
# Backend Telegram par défaut (factory)
# ---------------------------------------------------------------------

def _default_telegram_factory(token: str):
    """
    Essaie d’importer une implémentation TelegramAsync spécifique au repo.
    On attend une API min :
      - await tg.start()
      - await tg.stop()
      - await tg.send_message(text, chat_id=..., reply_markup: dict|None = None)
      - tg.set_message_handler(cb)
    """
    # Essais de chemins courants dans le projet
    candidates = (
        # ex: scalp/live/telegram_async.py
        ("scalp.live.telegram_async", "TelegramAsync"),
        ("scalp.integrations.telegram_async", "TelegramAsync"),
        ("telegram_async", "TelegramAsync"),
    )
    last_err = None
    for mod_name, cls_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            return cls(token)
        except Exception as e:
            last_err = e
            continue
    # Si rien n’est dispo, on lève une erreur claire
    raise RuntimeError(
        "Aucune implémentation TelegramAsync trouvée. "
        "Assure-toi d’avoir un module 'TelegramAsync' compatible (ex: scalp/live/telegram_async.py). "
        f"Dernière erreur: {last_err!r}"
    )

# ---------------------------------------------------------------------
# Helper pour créer rapidement un Notifier+Stream depuis l’orchestrateur
# ---------------------------------------------------------------------

async def build_notifier_and_stream() -> tuple[Notifier, CommandStream]:
    """
    Construit un TelegramNotifier si variables d’env sont présentes,
    sinon retourne un NullNotifier. Renvoie aussi son CommandStream.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if token:
        tn = TelegramNotifier(token=token, chat_id=int(chat) if chat else None)
        await tn.start()
        return tn, tn.command_stream
    else:
        nn = NullNotifier()
        await nn.start()
        # CommandStream indépendant (aucune source n’y pousse par défaut)
        cs = CommandStream()
        return nn, cs