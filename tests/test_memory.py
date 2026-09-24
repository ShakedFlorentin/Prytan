from core.knowledge.memory.store import add_memory, recall, MEMORY_DIR, INDEX

def test_add_writes_fact_and_index_line(tmp_path):
    f = add_memory(tmp_path, "Auth uses Argon2", "password hashing choice",
                   "We hash with argon2id, 64MB memory cost.", mtype="reference")
    assert f.exists()
    text = f.read_text()
    assert "name: auth-uses-argon2" in text and "type: reference" in text
    idx = (tmp_path / MEMORY_DIR / INDEX).read_text()
    assert "Auth uses Argon2" in idx and "(auth-uses-argon2.md)" in idx

def test_recall_finds_relevant_fact(tmp_path):
    add_memory(tmp_path, "Auth uses Argon2", "hashing", "argon2id hashing.")
    add_memory(tmp_path, "DB is SQLite", "database", "single-file sqlite db.")
    hits = recall(tmp_path, "argon2")
    assert hits and hits[0]["name"] == "auth-uses-argon2"

def test_add_is_idempotent_on_index(tmp_path):
    add_memory(tmp_path, "Same Fact", "d", "body")
    add_memory(tmp_path, "Same Fact", "d", "body")
    idx = (tmp_path / MEMORY_DIR / INDEX).read_text()
    assert idx.count("(same-fact.md)") == 1
