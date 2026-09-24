import json
from core.scheduler.skills_store import add_lesson, load_lessons, SKILLS_FILE


def test_add_lesson_creates_store(tmp_path):
    p = add_lesson(tmp_path, "Always parameterize cron times by config.", day="2026-06-21")
    assert p == tmp_path / SKILLS_FILE
    data = json.loads(p.read_text())
    assert data[0]["lesson"].startswith("Always parameterize")
    assert data[0]["day"] == "2026-06-21"


def test_add_lesson_appends_and_dedupes(tmp_path):
    add_lesson(tmp_path, "Lesson A", day="2026-06-21")
    add_lesson(tmp_path, "Lesson B", day="2026-06-21")
    add_lesson(tmp_path, "Lesson A", day="2026-06-22")   # exact dup text -> ignored
    lessons = load_lessons(tmp_path)
    assert [x["lesson"] for x in lessons] == ["Lesson A", "Lesson B"]


def test_load_lessons_empty_when_missing(tmp_path):
    assert load_lessons(tmp_path) == []


# I3 regression: non-list JSON must not crash add_lesson; must recover gracefully
def test_add_lesson_recovers_from_non_list_json(tmp_path):
    import json
    from pathlib import Path
    skills_file = tmp_path / SKILLS_FILE
    skills_file.parent.mkdir(parents=True, exist_ok=True)
    skills_file.write_text(json.dumps({"x": 1}))
    # add_lesson must not raise even though the file contains an object, not a list
    add_lesson(tmp_path, "New lesson after corrupt store.", day="2026-06-22")
    lessons = load_lessons(tmp_path)
    assert len(lessons) == 1
    assert lessons[0]["lesson"] == "New lesson after corrupt store."
