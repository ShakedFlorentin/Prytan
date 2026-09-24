from __future__ import annotations
import os
import re
import time
from pathlib import Path
from core.runtime.adapters.base import ChatAdapter


def _http_transport(token: str):
    """Real transport: POST to the Telegram Bot API. Imported lazily so the
    module has no hard network dependency for tests."""
    import json
    import urllib.request

    def call(method: str, params: dict) -> dict:
        url = f"https://api.telegram.org/bot{token}/{method}"
        data = json.dumps(params).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=65) as resp:   # pragma: no cover
            return json.loads(resp.read().decode())
    return call


def _http_file_download(token: str):
    """Real file download: GET the raw bytes from Telegram's separate file-serving
    host (NOT the bot-api JSON host `_http_transport` talks to). Imported lazily,
    injectable, for the same no-hard-network-dependency-in-tests reason."""
    import urllib.request

    def download(file_path: str) -> bytes:
        url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        with urllib.request.urlopen(url, timeout=60) as resp:   # pragma: no cover
            return resp.read()
    return download


class TelegramAdapter(ChatAdapter):
    """ChatAdapter over the Telegram Bot API. `transport(method, params)->dict`
    is injectable so tests never touch the network.

    Deploy note (spec §4.2): launch from the project root, not a transient cwd —
    a deleted cwd kills the long-running process."""

    def __init__(self, token: str, *, chat_id: int, transport=None,
                 file_download=None, uploads_dir=None):
        self.token = token
        self.chat_id = int(chat_id)
        self._transport = transport or _http_transport(token)
        self._file_download = file_download or _http_file_download(token)
        # Default lives beside perms.py's PERMS_DIR (".agent-runtime") — outside
        # the org write-scope dirs, so a downloaded attachment is never itself a
        # write-scope target.
        self._uploads_dir = Path(uploads_dir) if uploads_dir else Path(".agent-runtime") / "telegram-uploads"
        self._offset = 0

    @classmethod
    def from_env(cls, *, env=None, transport=None) -> "TelegramAdapter":
        env = os.environ if env is None else env
        token = env.get("TELEGRAM_BOT_TOKEN")
        chat_id = env.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in the env")
        return cls(token, chat_id=int(chat_id), transport=transport)

    def _save_attachment(self, file_id: str, suggested_name: str) -> str:
        """Download one document/photo via getFile + the file host, save it under
        uploads_dir, and return a note describing where it landed (or why it
        didn't) — so the orchestrator/agent sees it instead of the message being
        silently dropped, which was the bug: read() used to check only msg["text"],
        and a document/photo carries none (its caption lives in msg["caption"])."""
        info = self._transport("getFile", {"file_id": file_id})
        file_path = (info.get("result") or {}).get("file_path")
        if not file_path:
            return "[attached file failed to download: no file_path from getFile]"
        try:
            data = self._file_download(file_path)
        except Exception as exc:            # transient network error — never crash read()
            return f"[attached file failed to download: {exc}]"
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w.\-]", "_", Path(suggested_name).name) or Path(file_path).name
        dest = self._uploads_dir / f"{int(time.time())}_{safe_name}"
        dest.write_bytes(data)
        return f"[attached file saved to {dest} ({len(data)} bytes)]"

    def read(self) -> str | None:
        """Make exactly ONE getUpdates call. Advance offset past ALL updates in
        the batch, then return the last allowed-chat text found, or None.

        A document/photo message carries its own text in "caption", never "text"
        — and previously wasn't checked at all, so an attachment-only message
        (with or without a caption) was silently dropped. Now: caption stands in
        for text when text is empty, and any document/photo is downloaded and
        its saved path appended as a note, so it's never invisible to the
        orchestrator."""
        params = {"timeout": 60}
        if self._offset:
            params["offset"] = self._offset
        resp = self._transport("getUpdates", params)
        results = resp.get("result", [])
        if not results:
            return None
        found_text = None
        for upd in results:
            self._offset = max(self._offset, upd.get("update_id", 0) + 1)
            msg = upd.get("message") or {}
            if (msg.get("chat") or {}).get("id") != self.chat_id:
                continue
            text = (msg.get("text") or "").strip()
            caption = (msg.get("caption") or "").strip()
            note = ""
            doc = msg.get("document")
            photos = msg.get("photo")
            if doc:
                note = self._save_attachment(doc["file_id"], doc.get("file_name") or "file")
            elif photos:
                largest = max(photos, key=lambda p: p.get("file_size", 0))
                note = self._save_attachment(largest["file_id"], "photo.jpg")
            combined = text or caption
            if note:
                combined = f"{combined}\n\n{note}".strip() if combined else note
            if combined:
                found_text = combined
        return found_text

    def write(self, text: str) -> None:
        self._transport("sendMessage", {"chat_id": self.chat_id, "text": text})
