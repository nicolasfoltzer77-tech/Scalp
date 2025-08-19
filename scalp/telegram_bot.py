from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    import requests as _requests
    requests = _requests
except Exception:  # pragma: no cover
    class _Requests:
        def get(self, *a: Any, **k: Any) -> Any:  # pragma: no cover - fallback
            raise RuntimeError("requests.get unavailable")

        def post(self, *a: Any, **k: Any) -> Any:  # pragma: no cover - fallback
            raise RuntimeError("requests.post unavailable")

    requests = _Requests()  # type: ignore[assignment]


class TelegramBot:
    """Minimal Telegram bot using the HTTP API.


    The bot exposes a simple *menu* based interface with clickable buttons so
    users do not have to remember text commands.  A sub-menu lets the user set
    the risk level.

    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        client: Any,
        config: Dict[str, Any],
        risk_mgr: Any,
        *,
        requests_module: Any = requests,
    ) -> None:
        self.token = token
        self.chat_id = str(chat_id)
        self.client = client
        self.config = config
        self.risk_mgr = risk_mgr
        self.requests = requests_module
        self.last_update_id: Optional[int] = None
        self.stop_requested = False


        self.main_keyboard = [
            [{"text": "Positions ouvertes", "callback_data": "positions"}],
            [{"text": "Update Cryptos", "callback_data": "update"}],
            [{"text": "Réglages", "callback_data": "settings"}],
        ]
        self.settings_keyboard = [
            [{"text": "Stop trade", "callback_data": "stop"}],
            [{"text": "Réglage risk", "callback_data": "risk"}],
            [{"text": "Reset risk", "callback_data": "reset_risk"}],
            [{"text": "Arrêt bot", "callback_data": "shutdown"}],
            [{"text": "Reset total", "callback_data": "reset_all"}],
            [{"text": "Retour", "callback_data": "back"}],
        ]
        self.risk_keyboard = [
            [
                {"text": "🟢", "callback_data": "risk_green"},
                {"text": "🟠", "callback_data": "risk_orange"},
                {"text": "🔴", "callback_data": "risk_red"},
            ],
            [{"text": "Retour", "callback_data": "back"}],
        ]

        # Show menu on startup with zero PnL session
        self.send_main_menu(0.0)


    def _base_symbol(self, symbol: str) -> str:
        sym = symbol.replace("_", "")
        return sym[:-4] if sym.endswith("USDT") else sym

    def _build_stop_keyboard(self) -> list[list[Dict[str, str]]]:
        pos = self.client.get_positions()
        buttons: list[list[Dict[str, str]]] = []
        for p in pos.get("data", []):
            sym = p.get("symbol")
            if not sym:
                continue
            base = self._base_symbol(sym)
            # Use the full symbol in the callback so we can properly
            # identify the position to close.  Only the label shows the
            # base asset to keep the interface concise.
            buttons.append([{"text": base, "callback_data": f"stop_{sym}"}])
        buttons.append([{"text": "Tous", "callback_data": "stop_all"}])
        buttons.append([{"text": "Retour", "callback_data": "back"}])
        return buttons


    def _menu_text(self, session_pnl: float) -> str:
        assets = self.client.get_assets()
        equity = 0.0
        for row in assets.get("data", []):
            if row.get("currency") == "USDT":
                try:
                    equity = float(row.get("equity", 0.0))
                except Exception:
                    equity = 0.0
                break
        return (
            f"Solde: {equity} USDT\n"
            f"PnL session: {session_pnl} USDT\n"
            "Choisissez une option:"
        )

    def send_main_menu(self, session_pnl: float) -> None:
        self.send(self._menu_text(session_pnl), self.main_keyboard)

    def update_pairs(self) -> None:
        from bot import update as _update  # lazy import to avoid cycle

        _update(self.client, top_n=20, tg_bot=self)

    # ------------------------------------------------------------------
    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"


    def send(self, text: str, keyboard: Optional[list[list[Dict[str, str]]]] = None) -> None:
        payload: Dict[str, Any] = {"chat_id": self.chat_id, "text": text}
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}

        try:  # pragma: no cover - network
            self.requests.post(self._api_url("sendMessage"), json=payload, timeout=5)
        except Exception as exc:  # pragma: no cover - best effort
            logging.error("Telegram send error: %s", exc)

    def answer_callback(self, cb_id: str) -> None:
        payload = {"callback_query_id": cb_id}
        try:  # pragma: no cover - network
            self.requests.post(
                self._api_url("answerCallbackQuery"), json=payload, timeout=5
            )
        except Exception as exc:  # pragma: no cover - best effort
            logging.error("Telegram answerCallback error: %s", exc)


    # ------------------------------------------------------------------
    def fetch_updates(self) -> list[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if self.last_update_id is not None:
            params["offset"] = self.last_update_id + 1
        try:  # pragma: no cover - network
            r = self.requests.get(self._api_url("getUpdates"), params=params, timeout=5)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # pragma: no cover - best effort
            logging.error("Telegram getUpdates error: %s", exc)
            return []
        updates = data.get("result", [])
        if updates:
            self.last_update_id = updates[-1].get("update_id")
        return updates

    # ------------------------------------------------------------------
    def handle_updates(self, session_pnl: float) -> None:
        for update in self.fetch_updates():

            callback = update.get("callback_query")
            if callback:
                if str(callback.get("from", {}).get("id")) != self.chat_id:
                    continue
                data = callback.get("data", "")
                reply, kb = self.handle_callback(data, session_pnl)
                if reply:
                    self.send(reply, kb)
                cb_id = callback.get("id")
                if cb_id:
                    self.answer_callback(cb_id)
                continue


            msg = update.get("message") or {}
            chat = msg.get("chat") or {}
            if str(chat.get("id")) != self.chat_id:
                continue

            # Any text message triggers the main menu with balance and PnL
            self.send_main_menu(session_pnl)

    # ------------------------------------------------------------------
    def handle_callback(
        self, data: str, session_pnl: float
    ) -> tuple[Optional[str], Optional[list[list[Dict[str, str]]]]]:
        if not data:
            return None, None
        if data == "balance":
            assets = self.client.get_assets()
            equity = 0.0
            for row in assets.get("data", []):
                if row.get("currency") == "USDT":
                    try:
                        equity = float(row.get("equity", 0.0))
                    except Exception:
                        equity = 0.0
                    break

            return f"Solde: {equity} USDT", self.main_keyboard
        if data == "positions":
            pos = self.client.get_positions()
            lines = []
            for p in pos.get("data", []):
                symbol = p.get("symbol", "")
                base = self._base_symbol(symbol)
                side = p.get("side")
                vol = p.get("vol")
                pnl = p.get("pnl_usd")
                if pnl is None:
                    pnl = p.get("pnl")
                pnl_pct = p.get("pnl_pct")
                line = f"{base} {side} {vol}"
                if pnl is not None and pnl_pct is not None:
                    line += f"\nPnL: {pnl} USDT ({pnl_pct}%)"
                lines.append(line)
            if not lines:

                return "Aucune position ouverte", self.main_keyboard
            return "Positions:\n" + "\n".join(lines), self.main_keyboard
        if data == "pnl":
            return f"PnL session: {session_pnl} USDT", self.main_keyboard
        if data == "risk":
            return "Choisissez le niveau de risque:", self.risk_keyboard
        if data == "settings":
            return "Réglages:", self.settings_keyboard
        if data == "reset_risk":
            try:
                self.risk_mgr.reset_day()
                return "Risque réinitialisé", self.settings_keyboard
            except Exception:
                return "Erreur reset risque", self.settings_keyboard
        if data == "update":
            try:
                self.update_pairs()
                return "Liste cryptos mise à jour", self.main_keyboard
            except Exception:
                return "Erreur mise à jour", self.main_keyboard
        if data.startswith("risk"):
            mapping = {
                "risk_green": 1,
                "risk_orange": 2,
                "risk_red": 3,
            }
            lvl = mapping.get(data)
            if lvl:
                self.config["RISK_LEVEL"] = lvl
                return f"Niveau de risque réglé sur {lvl}", self.main_keyboard
            return "Niveau de risque inchangé", self.main_keyboard

        if data == "reset_all":
            try:
                self.client.close_all_positions()
                self.risk_mgr.reset_day()
                return "Positions et risque réinitialisés", self.settings_keyboard
            except Exception:
                return "Erreur reset total", self.settings_keyboard

        if data == "stop":
            return "Choisissez la position à fermer:", self._build_stop_keyboard()
        if data == "stop_all":
            try:
                self.client.close_all_positions()
                return "Toutes les positions fermées", self.settings_keyboard
            except Exception:
                return "Erreur fermeture positions", self.settings_keyboard
        if data.startswith("stop_"):
            sym = data[5:]
            try:
                self.client.close_position(sym)
                return f"Position {sym} fermée", self.settings_keyboard
            except Exception:
                return f"Erreur fermeture {sym}", self.settings_keyboard

        if data == "shutdown":
            self.stop_requested = True
            return "Arrêt du bot demandé", self.settings_keyboard

        if data == "back":
            return self._menu_text(session_pnl), self.main_keyboard
        return None, None


def init_telegram_bot(client: Any, config: Dict[str, Any], risk_mgr: Any) -> Optional[TelegramBot]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return TelegramBot(token, chat_id, client, config, risk_mgr)
    return None
