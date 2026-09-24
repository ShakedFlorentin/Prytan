"""Relevance-gated recall: the gate, the disk sources, and the memory hooks."""
import json
import subprocess
import sys
from pathlib import Path

from core.knowledge.memory import hook
from core.knowledge.memory.sources import TIER_CHATTER, author_of, gather
from core.knowledge.memory.store import add_memory, recall
from core.knowledge.relevance import (
    Candidate, best_line, evaluate, render, score, select, stem, tokenize,
)

REPO = Path(__file__).resolve().parent.parent


def _cand(cid, text, tier=3):
    return Candidate(id=cid, text=text, source="logs", tier=tier)


def _filler(n=200):
    return [_cand(f"f{i}", f"weekly report fix update write notes item {i}") for i in range(n)]


# ── tokenize / gate ─────────────────────────────────────────────────────────

def test_tokenize_strips_punctuation_stopwords_keeps_numbers_and_ids():
    assert tokenize("Why does the Argon2, (hit) twice in 2026?") == ["argon2", "hit", "twice", "2026"]
    assert tokenize("Don’t restart him, it's in a run") == ["restart", "run"]
    toks = tokenize("JIRA-39 and auth_v2 but arc-to-source")
    assert "jira-39" in toks and "auth_v2" in toks and "arc-to-source" not in toks


def test_one_shared_word_does_not_pass():
    pool = _filler() + [_cand("org", "org health report for the week")]
    assert score("argon2 duplicate hashes report", pool) == []


def test_whole_word_only():
    pool = _filler() + [_cand("p", "prefix handling in the argon2 prefix")]
    assert score("fix argon2", pool) == []


def test_common_words_alone_never_pass():
    assert score("write a report", _filler() + [_cand("x", "write the report")]) == []


def test_chatty_prompt_injects_nothing():
    pool = _filler() + [_cand("x", "continue where we left off yesterday")]
    assert score("hi, can you continue where we left off?", pool) == []


def test_relevant_memory_ranks_first_and_curated_beats_chatter():
    curated = _cand("mem", "argon2 pbkdf_v2 migration", tier=0)
    chatter = _cand("standup", "argon2 pbkdf_v2 migration notes", tier=TIER_CHATTER)
    hits = score("argon2 pbkdf_v2 migration notes", _filler() + [chatter, curated])
    assert [c.id for _, c, _ in hits] == ["mem", "standup"]


def test_identifier_parts_match_but_not_inside_words():
    pool = _filler() + [_cand("rt", "worker runs on python3.13 with MAX_RETRY set"),
                        _cand("pre", "prefix fixture python")]
    assert [c.id for _, c, _ in score("retry python", pool)] == ["rt"]


def test_word_forms_match():
    assert stem("blocked") == "block" and stem("running") == "run" and stem("status") == "status"
    pool = _filler() + [_cand("s", "the deploy is blocking on a migration command")]
    assert [c.id for _, c, _ in score("deploy blocked migration", pool)] == ["s"]


def test_short_words_take_plurals_and_y_forms_meet():
    pool = _filler() + [_cand("r", "auth_v2 refresh caps retries via MAX_RETRY gates")]
    assert [c.id for _, c, _ in score("why does auth_v2 cap retry gate", pool)] == ["r"]
    assert stem("retries") == "retry"
    assert score("fix latest", _filler() + [_cand("x", "prefix fixture tests")]) == []


def test_stop_hook_redacts_real_secret_shapes_but_keeps_paths():
    # Fake secrets, assembled at runtime so repo secret scanners don't flag the source.
    pem = "-----BEGIN RSA " + "PRIVATE KEY----- MIIEpAIBAAKCAQEA1234 -----END RSA " + "PRIVATE KEY-----"
    for secret in ["eyJ" + "hbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJ", pem,
                   "sk_" + "live_51HxYzAbCdEfGhIjKlMn", "AI" + "zaSyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUv",
                   "9B3CaDMzg-bzHxGb28K0KMlW6-CRz01427UhQKr1tkY="]:
        out = hook._clean(f"before {secret} after")
        assert "[REDACTED]" in out and secret[:12] not in out, secret
    assert "hunter2" not in hook._clean("postgres://admin:hunter2@db.internal/app")
    keep = "core/knowledge/memory/hook.py and test_short_words_take_plurals_v2"
    assert hook._clean(keep) == keep


def test_stop_hook_dedupes_the_same_turn_across_sessions(tmp_path):
    t = _transcript(tmp_path, "same question", "same answer")
    assert hook.remember({"transcript_path": str(t), "session_id": "a"}, tmp_path) is True
    assert hook.remember({"transcript_path": str(t), "session_id": "b"}, tmp_path) is False


def test_title_match_outranks_body_mention():
    body = _cand("body", "scrypt pbkdf_v2 and many other words", tier=0)
    titled = Candidate(id="titled", text="details follow", source="logs", tier=0,
                       title="scrypt pbkdf_v2 migration")
    assert score("scrypt pbkdf_v2", _filler() + [body, titled])[0][1].id == "titled"


def test_long_prompt_bar_is_lower():
    target = _cand("t", "fable limit skills agents", tier=0)  # ~55%: under 0.6, over long bar
    prompt = "write the right skills for my agents so when I hit my fable limit I get best results"
    assert [c.id for _, c, _ in score(prompt, _filler() + [target])] == ["t"]


def test_uncurated_log_needs_title_match_or_high_coverage():
    log = _cand("log", "scrypt pbkdf_v2 argon2 and more")
    titled = Candidate(id="titled", text="scrypt pbkdf_v2 argon2", source="logs", tier=3,
                       title="scrypt rollout")
    ids = [c.id for _, c, _ in score("scrypt pbkdf_v2 argon2 bcrypt", _filler() + [log, titled])]
    assert ids == ["titled"]


def test_select_keeps_one_per_family():
    logs = [Candidate(id=f"l{i}", text="scrypt pbkdf_v2 wave", source="logs", author="devops")
            for i in range(3)]
    other = Candidate(id="o", text="scrypt pbkdf_v2 wave", source="logs", author="backend")
    picks = select("scrypt pbkdf_v2 wave", _filler() + logs + [other], n=3)
    assert sorted(c.author for _, c, _ in picks) == ["backend", "devops"]


def test_best_line_render_and_evaluate():
    c = Candidate(id="m", source="memory", tier=0, title="Worker runtime", path="memory/rt.md",
                  text="---\ndescription: x\n---\nintro text here\nworker runs on python3.13 only\n")
    assert best_line(c, ["python", "worker"]) == "worker runs on python3.13 only"
    assert "> worker runs on python3.13 only" in render([(1.0, c, ["python", "worker"])])
    res = evaluate([{"prompt": "worker python3.13 runtime", "expect": ["rt.md"]},
                    {"prompt": "keep going", "expect": []}], _filler() + [c])
    assert res["hit@1"] == 1.0 and res["clean"] == 1.0


def test_eval_cli(tmp_path):
    add_memory(tmp_path, "Auth uses Argon2", "hashing choice", "argon2id with 64MB memory cost")
    labels = tmp_path / "labels.jsonl"
    labels.write_text(json.dumps({"prompt": "argon2id memory cost", "expect": ["auth-uses-argon2"]})
                      + "\n" + json.dumps({"prompt": "keep going", "expect": []}) + "\n")
    out = subprocess.run([sys.executable, "-m", "core.knowledge.memory", "eval", str(labels),
                          "--root", str(tmp_path), "--lexical"], text=True, capture_output=True,
                         cwd=REPO)
    assert out.returncode == 0 and "hit@1 100%" in out.stdout and "clean 100%" in out.stdout


def test_scattered_words_in_a_long_document_do_not_pass():
    journal = "\n\n".join(
        f"entry {i}: " + w + " " + "unrelated words here " * 8
        for i, w in enumerate(["scrypt", "pbkdf_v2", "argon2", "bcrypt"])
    )
    together = _cand("near", "scrypt pbkdf_v2 argon2 bcrypt in one passage")
    ids = [c.id for _, c, _ in score("scrypt pbkdf_v2 argon2 bcrypt",
                                     _filler() + [_cand("journal", journal), together])]
    assert ids == ["near"]


class _FakeEmbedder:
    def __init__(self, table=None):
        self.table = table

    def similarity(self, prompt, docs):
        return None if self.table is None else {d: self.table.get(d, 0.2) for d in docs}


def test_semantic_rejects_word_match_without_meaning_and_falls_back():
    mem = _cand("m", "scrypt pbkdf_v2 argon2 migration", tier=0)
    pool = _filler() + [mem]
    assert select("scrypt pbkdf_v2 argon2", pool, embedder=_FakeEmbedder({"m": 0.3})) == []
    assert select("scrypt pbkdf_v2 argon2", pool, embedder=_FakeEmbedder({"m": 0.5}))
    assert select("scrypt pbkdf_v2 argon2", pool, embedder=_FakeEmbedder(None))  # words decide


def test_semantic_finds_memory_with_no_shared_words():
    mem = Candidate(id="m", text="the host kernel-panicked twice", source="memory", tier=0)
    assert select("machine crashed hard overnight", _filler() + [mem]) == []
    picks = select("machine crashed hard overnight", _filler() + [mem],
                   embedder=_FakeEmbedder({"m": 0.6}))
    assert [c.id for _, c, _ in picks] == ["m"]


def test_embedder_backs_off_after_failure_but_not_on_document_budget(tmp_path, monkeypatch):
    import time
    from array import array

    from core.knowledge.semantic import Embedder

    down = Embedder(tmp_path / "emb", url="http://127.0.0.1:9", timeout=0.5)
    assert down.similarity("q", {"a": "t"}) is None
    again = Embedder(tmp_path / "emb", url="http://127.0.0.1:9", timeout=0.5)
    start = time.monotonic()
    assert again.similarity("q", {"a": "t"}) is None and time.monotonic() - start < 0.05

    ok = Embedder(tmp_path / "emb2")
    monkeypatch.setattr(ok, "_embed", lambda texts, timeout, probe=True:
                        [array("f", [1.0, 0.0])] if probe else None)
    assert ok.similarity("q", {"a": "new text"}) == {} and not ok._backing_off()


def test_embedder_unreachable_is_fast_and_warm_cli_reports_it(tmp_path):
    import time

    from core.knowledge.semantic import Embedder

    emb = Embedder(tmp_path / "emb", url="http://127.0.0.1:9", timeout=0.5)
    start = time.monotonic()
    assert emb.similarity("anything", {"a": "text"}) is None and time.monotonic() - start < 2
    add_memory(tmp_path, "Auth uses Argon2", "hashing", "argon2id")
    out = subprocess.run([sys.executable, "-m", "core.knowledge.memory", "warm", "--root",
                          str(tmp_path)], text=True, capture_output=True, cwd=REPO,
                         env={"PATH": "/usr/bin:/bin", "OLLAMA_HOST": "http://127.0.0.1:9"})
    assert out.returncode == 0 and "service unavailable" in out.stdout


def _no_embedder(*a, **k):
    raise AssertionError("semantic recall must not run unless the project opts in")


def test_semantic_recall_is_off_by_default(tmp_path, monkeypatch):
    from core.knowledge.memory import sources

    add_memory(tmp_path, "Auth uses Argon2", "hashing choice", "argon2id with 64MB memory cost")
    assert sources.semantic_enabled(tmp_path) is False  # no config.yaml at all
    (tmp_path / "config.yaml").write_text("project_name: x\n")
    assert sources.semantic_enabled(tmp_path) is False  # config without the key
    monkeypatch.setattr(hook, "embedder", _no_embedder)
    assert "auth-uses-argon2" in hook.recall_block(tmp_path, "what argon2id memory cost")


def test_semantic_recall_opt_in_uses_the_embedder(tmp_path, monkeypatch):
    from core.knowledge.memory import sources

    (tmp_path / "config.yaml").write_text("memory:\n  semantic: true\n")
    assert sources.semantic_enabled(tmp_path) is True
    used = []

    class _Emb:
        def similarity(self, prompt, docs):
            used.append(prompt)
            return None  # service down → words decide

    monkeypatch.setattr(hook, "embedder", lambda root: _Emb())
    add_memory(tmp_path, "Auth uses Argon2", "hashing choice", "argon2id with 64MB memory cost")
    hook.recall_block(tmp_path, "what argon2id memory cost")
    assert used == ["what argon2id memory cost"]


def test_session_start_warms_only_when_opted_in(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(hook, "warm_in_background", lambda root: calls.append(root))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO('{"hook_event_name":"SessionStart"}'))
    hook.main()
    assert calls == []
    (tmp_path / "config.yaml").write_text("memory:\n  semantic: true\n")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO('{"hook_event_name":"SessionStart"}'))
    hook.main()
    assert calls == [tmp_path]


def test_new_project_config_shows_the_switch_off(tmp_path):
    from core import onboarding as ob

    ob.config_set(tmp_path, "project_name", "x")
    assert "semantic: false" in (tmp_path / "config.yaml").read_text()


# ── sources ─────────────────────────────────────────────────────────────────

def test_author_from_folder_or_dated_filename_never_year(tmp_path):
    base = tmp_path / ".logs"
    agents = {"atlas", "backend"}
    assert author_of(base / "backend" / "2026-06-20-note.md", base, agents) == "backend"
    assert author_of(base / "2026-06-22-atlas-plan.md", base, agents) == "atlas"
    assert author_of(base / "2026-08-10-org-health.md", base, agents) == ""


def test_gather_reads_all_sources_fresh(tmp_path):
    add_memory(tmp_path, "Auth uses Argon2", "hashing choice", "argon2id, 64MB")
    log = tmp_path / ".logs" / "backend" / "2026-09-01-auth.md"
    log.parent.mkdir(parents=True)
    log.write_text("# Auth migration\n" + "x " * 400 + "late_marker")
    (tmp_path / ".handoffs").mkdir()
    (tmp_path / ".handoffs" / "2026-09-02-atlas-daily-standup.md").write_text("argon2")
    (tmp_path / ".logs" / "conversations.jsonl").write_text(
        json.dumps({"session_id": "old", "prompt": "argon2 q", "reply": "a"}) + "\n"
        + json.dumps({"session_id": "now", "prompt": "argon2 now", "reply": "a"}) + "\n")
    by_id = {c.id: c for c in gather(tmp_path, exclude_session="now")}
    assert "memory:memory/auth-uses-argon2.md" in by_id
    assert not any(k.endswith("MEMORY.md") for k in by_id)
    entry = by_id["logs:.logs/backend/2026-09-01-auth.md"]
    assert entry.author == "backend" and "late_marker" in entry.text
    assert by_id["handoffs:.handoffs/2026-09-02-atlas-daily-standup.md"].tier == TIER_CHATTER
    convs = [c for c in by_id.values() if c.source == "conversation"]
    assert len(convs) == 1 and "argon2 q" in convs[0].text
    log.unlink()
    assert "logs:.logs/backend/2026-09-01-auth.md" not in {c.id for c in gather(tmp_path)}


def test_recall_multiword_query_needs_coverage(tmp_path):
    add_memory(tmp_path, "Auth uses Argon2", "hashing", "argon2id hashing with 64MB memory")
    add_memory(tmp_path, "DB is SQLite", "database", "single-file sqlite db, hashing none")
    hits = recall(tmp_path, "argon2id hashing")
    assert [h["name"] for h in hits] == ["auth-uses-argon2"]


# ── hooks ───────────────────────────────────────────────────────────────────

def test_prompt_hook_injects_only_relevant(tmp_path):
    add_memory(tmp_path, "Auth uses Argon2", "hashing choice", "argon2id with 64MB memory cost")
    q = "what argon2id memory cost do we use"
    assert "auth-uses-argon2" in hook.recall_block(tmp_path, q, semantic=False)
    assert hook.recall_block(tmp_path, "hi, can you continue where we left off?", semantic=False) == ""


def _transcript(tmp_path, prompt, reply):
    lines = [
        {"type": "user", "message": {"content": "<system-reminder>x</system-reminder>" + prompt}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "out"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(x) for x in lines))
    return t


def test_stop_hook_saves_turn_once_capped_redacted_and_gitignored(tmp_path):
    t = _transcript(tmp_path, "why argon2 API_KEY=abc123secretvalue", "because " + "y" * 900)
    event = {"transcript_path": str(t), "session_id": "s1"}
    assert hook.remember(event, tmp_path) is True
    assert hook.remember(event, tmp_path) is False
    store = tmp_path / ".logs" / "conversations.jsonl"
    rec = json.loads(store.read_text().splitlines()[0])
    assert len(store.read_text().splitlines()) == 1
    assert rec["prompt"].startswith("why argon2") and "system-reminder" not in rec["prompt"]
    assert "abc123secretvalue" not in rec["prompt"] and "[REDACTED]" in rec["prompt"]
    assert len(rec["reply"]) == 500
    assert (tmp_path / ".logs" / ".gitignore").read_text().strip() == "conversations.jsonl"


def test_hook_script_runs_standalone_and_never_fails(tmp_path):
    add_memory(tmp_path, "Auth uses Argon2", "hashing choice", "argon2id with 64MB memory cost")
    script = REPO / "core" / "knowledge" / "memory" / "hook.py"
    ev = {"hook_event_name": "UserPromptSubmit", "prompt": "argon2id memory cost",
          "cwd": str(tmp_path)}
    env = {"PATH": "/usr/bin:/bin", "OLLAMA_HOST": "http://127.0.0.1:9"}  # words-only path
    out = subprocess.run([sys.executable, str(script)], input=json.dumps(ev), text=True,
                         capture_output=True, cwd=tmp_path, env=env)
    assert out.returncode == 0 and "auth-uses-argon2" in out.stdout
    bad = subprocess.run([sys.executable, str(script)], input="not json", text=True,
                         capture_output=True, cwd=tmp_path)
    assert bad.returncode == 0 and bad.stdout == ""


def test_plugin_wires_memory_hooks():
    h = json.loads((REPO / "hooks" / "hooks.json").read_text())["hooks"]
    for event in ("UserPromptSubmit", "Stop", "SessionStart"):
        assert "core/knowledge/memory/hook.py" in json.dumps(h[event])
