import pytest
from core.runtime.adapters.base import ChatAdapter
from core.runtime.adapters.telegram import TelegramAdapter


class FakeTransport:
    """Fake Telegram transport. `batches` is a list of batches; each batch is a
    list of update dicts returned for one getUpdates call. Tracks all
    getUpdates calls in `get_calls` for offset-advancement assertions.
    `files` maps file_id -> file_path, used to answer getFile."""

    def __init__(self, batches, files=None):
        self._batches = list(batches)
        self._files = files or {}
        self.sent = []
        self.get_calls = []

    def __call__(self, method, params):
        if method == "getUpdates":
            self.get_calls.append(dict(params))
            if not self._batches:
                return {"ok": True, "result": []}
            return {"ok": True, "result": self._batches.pop(0)}
        if method == "sendMessage":
            self.sent.append(params)
            return {"ok": True}
        if method == "getFile":
            file_path = self._files.get(params["file_id"])
            if file_path is None:
                return {"ok": False}
            return {"ok": True, "result": {"file_path": file_path}}
        raise AssertionError(f"unexpected method {method}")


class FakeFileDownload:
    """Fake file-host downloader. `content` maps file_path -> bytes."""

    def __init__(self, content):
        self._content = content
        self.calls = []

    def __call__(self, file_path):
        self.calls.append(file_path)
        return self._content[file_path]


def _update(update_id, chat_id, text):
    return {"update_id": update_id,
            "message": {"chat": {"id": chat_id}, "text": text}}


def _doc_update(update_id, chat_id, file_id, file_name, *, caption=None):
    msg = {"chat": {"id": chat_id},
           "document": {"file_id": file_id, "file_name": file_name}}
    if caption is not None:
        msg["caption"] = caption
    return {"update_id": update_id, "message": msg}


def test_is_a_chat_adapter():
    assert issubclass(TelegramAdapter, ChatAdapter)


def test_read_returns_text_for_allowed_chat():
    # Single batch with one update for the allowed chat
    t = FakeTransport([[_update(1, 42, "hello")]])
    a = TelegramAdapter("TOK", chat_id=42, transport=t)
    assert a.read() == "hello"


def test_read_ignores_other_chats():
    # Both updates in ONE batch: chat 999 (filtered) and chat 42 (allowed)
    batch = [_update(1, 999, "intruder"), _update(2, 42, "ok")]
    t = FakeTransport([batch])
    a = TelegramAdapter("TOK", chat_id=42, transport=t)
    assert a.read() == "ok"          # skips chat 999, returns the allowed one


def test_read_returns_none_when_no_updates():
    t = FakeTransport([])
    a = TelegramAdapter("TOK", chat_id=42, transport=t)
    assert a.read() is None


def test_write_sends_to_chat():
    t = FakeTransport([])
    a = TelegramAdapter("TOK", chat_id=42, transport=t)
    a.write("reply text")
    assert t.sent == [{"chat_id": 42, "text": "reply text"}]


def test_offset_advances_past_consumed_updates():
    # First call returns update_id 5; second call must use offset=6
    t = FakeTransport([[_update(5, 42, "a")], []])
    a = TelegramAdapter("TOK", chat_id=42, transport=t)
    a.read()                             # consumes update_id 5, sets offset to 6
    a.read()                             # second poll — should pass offset=6
    assert len(t.get_calls) == 2
    assert t.get_calls[1].get("offset") == 6     # last update_id + 1


def test_from_env_reads_token_and_chat(monkeypatch):
    from core.runtime.adapters.telegram import TelegramAdapter
    env = {"TELEGRAM_BOT_TOKEN": "ENVTOK", "TELEGRAM_CHAT_ID": "77"}
    a = TelegramAdapter.from_env(env=env, transport=FakeTransport([]))
    assert a.token == "ENVTOK" and a.chat_id == 77


def test_from_env_missing_token_raises():
    with pytest.raises(ValueError):
        TelegramAdapter.from_env(env={}, transport=FakeTransport([]))


def test_document_with_caption_is_not_dropped(tmp_path):
    # Regression: read() used to check only msg["text"], which is always empty
    # for a document message (its caption lives in msg["caption"]) — the whole
    # message was silently swallowed.
    batch = [_doc_update(1, 42, "fid1", "notes.zip", caption="see attached")]
    t = FakeTransport([batch], files={"fid1": "documents/notes.zip"})
    dl = FakeFileDownload({"documents/notes.zip": b"zip-bytes"})
    a = TelegramAdapter("TOK", chat_id=42, transport=t, file_download=dl,
                        uploads_dir=tmp_path)
    result = a.read()
    assert result.startswith("see attached")
    assert "attached file saved to" in result
    saved = list(tmp_path.iterdir())
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"zip-bytes"


def test_document_with_no_caption_still_surfaces(tmp_path):
    # No text AND no caption — must not come back as None just because the
    # attachment carries no words of its own.
    batch = [_doc_update(1, 42, "fid1", "report.md")]
    t = FakeTransport([batch], files={"fid1": "documents/report.md"})
    dl = FakeFileDownload({"documents/report.md": b"content"})
    a = TelegramAdapter("TOK", chat_id=42, transport=t, file_download=dl,
                        uploads_dir=tmp_path)
    result = a.read()
    assert result is not None
    assert "attached file saved to" in result


def test_photo_picks_largest_size(tmp_path):
    msg = {"chat": {"id": 42},
           "photo": [{"file_id": "small", "file_size": 100},
                     {"file_id": "big", "file_size": 900}]}
    batch = [{"update_id": 1, "message": msg}]
    t = FakeTransport([batch], files={"big": "photos/big.jpg"})
    dl = FakeFileDownload({"photos/big.jpg": b"jpeg-bytes"})
    a = TelegramAdapter("TOK", chat_id=42, transport=t, file_download=dl,
                        uploads_dir=tmp_path)
    result = a.read()
    assert "attached file saved to" in result
    assert dl.calls == ["photos/big.jpg"]


def test_attachment_download_failure_does_not_crash(tmp_path):
    # getFile returns ok:false (e.g. expired file_id) — read() must return a
    # note, never raise, never silently drop the turn.
    batch = [_doc_update(1, 42, "missing", "x.bin")]
    t = FakeTransport([batch], files={})
    a = TelegramAdapter("TOK", chat_id=42, transport=t,
                        file_download=FakeFileDownload({}), uploads_dir=tmp_path)
    result = a.read()
    assert result is not None
    assert "failed to download" in result
