"""
semantic.py — meaning-level relevance for prompt-time recall, via a local Ollama
embedding model.

Word overlap can say whether a memory CONTAINS the prompt's words, never whether
it is ABOUT them: "send another agent without context to test it" can share four
words with an unrelated lesson. The embedding check is what decides relevance;
the lexical gate (relevance.py) only proposes candidates.

Optional: needs a local Ollama with an embedding model (`ollama pull
embeddinggemma`). Without it, recall uses the lexical gate alone.

  • stdlib only (urllib + array) — no numpy/torch in the hook's import path
  • vectors cached on disk, one small file per (model, text) hash, so a memory is
    embedded once and every later prompt costs one query embedding (~65 ms)
  • hard time budget: if Ollama is down, slow, or the model is missing, callers
    get None and fall back to the lexical gate — recall never blocks a prompt
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.request
from array import array
from pathlib import Path

DEFAULT_MODEL = os.environ.get("MEMO_EMBED_MODEL", "embeddinggemma")
DEFAULT_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# embeddinggemma is trained with these task prefixes; they widen the gap between
# related and unrelated pairs (measured: related 0.65-0.72, unrelated <= 0.35).
QUERY_PREFIX = "task: search result | query: "


def doc_text(title: str, body: str) -> str:
    return f"title: {title or 'none'} | text: {body}"


def _unit(vec: list[float]) -> array:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return array("f", (x / norm for x in vec))


def _dot(a: array, b: array) -> float:
    return sum(x * y for x, y in zip(a, b))


class Embedder:
    """Cosine similarity between a prompt and candidate texts, or None when the
    embedding service is unavailable."""

    def __init__(
        self,
        cache_dir: Path,
        model: str = DEFAULT_MODEL,
        url: str = DEFAULT_URL,
        timeout: float = 1.5,
        max_new: int = 6,
    ):
        self.model = model
        self.url = url.rstrip("/")
        if not self.url.startswith("http"):
            self.url = "http://" + self.url
        self.timeout = timeout  # seconds, per call AND total per similarity()
        self.max_new = max_new  # uncached texts embedded per prompt
        self.dir = Path(cache_dir) / model.replace(":", "_").replace("/", "_")
        self.dead = False  # set after a failed call: skip Ollama for this process

    # ── cache ───────────────────────────────────────────────────────────────
    def _key(self, text: str) -> Path:
        return self.dir / (hashlib.sha1(text.encode()).hexdigest() + ".f32")

    def _load(self, text: str) -> array | None:
        p = self._key(text)
        try:
            a = array("f")
            a.frombytes(p.read_bytes())
            return a
        except OSError:
            return None

    def _save(self, text: str, vec: array) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            ignore = self.dir.parent / ".gitignore"
            if not ignore.exists():
                ignore.write_text("*\n")  # the cache never belongs in git
            self._key(text).write_bytes(vec.tobytes())
        except OSError:
            pass

    # ── service ─────────────────────────────────────────────────────────────
    def _embed(self, texts: list[str], timeout: float) -> list[array] | None:
        if self.dead or not texts or timeout <= 0:
            return None
        body = json.dumps({"model": self.model, "input": texts}).encode()
        req = urllib.request.Request(
            f"{self.url}/api/embed", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                vecs = json.loads(resp.read())["embeddings"]
        except Exception:  # noqa: BLE001 — any failure means "no semantic signal"
            self.dead = True
            return None
        return [_unit(v) for v in vecs]

    def similarity(self, prompt: str, docs: dict[str, str]) -> dict[str, float] | None:
        """{doc_id: cosine} for every doc whose vector is cached or could be made
        within budget; None if the prompt itself could not be embedded. Docs that
        missed the budget are simply absent — callers treat them as unknown."""
        start = time.monotonic()
        q = self._embed([QUERY_PREFIX + prompt], self.timeout)
        if not q:
            return None
        qv = q[0]
        out, missing = {}, []
        for did, text in docs.items():
            v = self._load(text)
            if v is not None and len(v) == len(qv):
                out[did] = _dot(qv, v)
            else:
                missing.append((did, text))
        batch = missing[: self.max_new]
        left = self.timeout - (time.monotonic() - start)
        vecs = self._embed([t for _, t in batch], left) if batch else None
        for (did, text), v in zip(batch, vecs or []):
            self._save(text, v)
            out[did] = _dot(qv, v)
        return out

    def warm(self, texts: list[str], batch: int = 16) -> int:
        """Embed every uncached text (no time budget). Returns how many were added."""
        todo = [t for t in dict.fromkeys(texts) if not self._key(t).exists()]
        done = 0
        for i in range(0, len(todo), batch):
            chunk = todo[i : i + batch]
            vecs = self._embed(chunk, timeout=120)
            if not vecs:
                break
            for t, v in zip(chunk, vecs):
                self._save(t, v)
            done += len(chunk)
        return done
