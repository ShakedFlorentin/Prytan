#!/usr/bin/env python3
"""
Skill Compiler — nightly job that reflects on recent agent activity and
extracts durable lessons using `claude -p`.

Safe to run as a cron job. Never corrupts existing skills.json on failure.

Usage:
  python3 scripts/skill_compiler.py
"""

import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX_DIR = os.path.join(BASE_DIR, ".agent-inbox")
LOGS_DIR = os.path.join(BASE_DIR, ".agent-logs")
SKILLS_FILE = os.path.join(LOGS_DIR, "skills.json")
CRON_LOG = os.path.join(BASE_DIR, "cron.log")

MAX_SKILLS = 50
CLAUDE_DIGEST_COUNT = 3


def _load_skills():
    if not os.path.exists(SKILLS_FILE):
        return []
    try:
        with open(SKILLS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_skills(skills):
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        json.dump(skills, f, indent=2)


def _read_recent_digests():
    """Read the last CLAUDE_DIGEST_COUNT dispatch/standup digests from .agent-inbox/."""
    pattern = os.path.join(INBOX_DIR, "*.md")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    files = files[:CLAUDE_DIGEST_COUNT]

    chunks = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(4000)  # cap per file
            chunks.append(f"=== {os.path.basename(path)} ===\n{content}")
        except OSError:
            pass
    return "\n\n".join(chunks)


def _read_cron_tail():
    if not os.path.exists(CRON_LOG):
        return ""
    try:
        with open(CRON_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-100:])
    except OSError:
        return ""


def _build_prompt(digests, cron_tail):
    return f"""You are a skill compiler for an agent org. Review the recent activity below and extract durable lessons that would help agents do better work.

Return ONLY a JSON array of lesson objects. No prose, no markdown fences — raw JSON only.

Each lesson object has exactly these fields:
- "id": kebab-case slug (unique, descriptive)
- "kind": one of "intent_mapping" | "constraint" | "failure_pattern" | "scope_hint"
- "pattern": what situation triggers this lesson (1 sentence)
- "guidance": what to do differently (1-2 sentences, concrete)
- "agent": agent name this applies to, or null if general
- "confidence": float 0.0-1.0

Extract 3-8 lessons. Only include lessons with confidence >= 0.5. If there is nothing meaningful to extract, return an empty array [].

=== RECENT DIGESTS ===
{digests}

=== CRON LOG TAIL ===
{cron_tail}
"""


def _run_claude(prompt):
    """Run claude -p with the given prompt. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if not output:
            return None
        # Strip any accidental markdown fences
        if output.startswith("```"):
            lines = output.splitlines()
            # drop first and last fence lines
            inner = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block or not line.startswith("```"):
                    inner.append(line)
            output = "\n".join(inner).strip()
        return json.loads(output)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def _merge_skills(existing, new_lessons):
    """Merge new lessons into existing, deduplicating by id. Cap at MAX_SKILLS."""
    existing_ids = {s.get("id") for s in existing}
    for lesson in new_lessons:
        lesson_id = lesson.get("id")
        if not lesson_id:
            continue
        if lesson_id in existing_ids:
            # Update in place
            for i, s in enumerate(existing):
                if s.get("id") == lesson_id:
                    existing[i] = lesson
                    break
        else:
            existing.append(lesson)
            existing_ids.add(lesson_id)

    # If over cap, drop lowest-confidence entries
    if len(existing) > MAX_SKILLS:
        existing.sort(key=lambda s: s.get("confidence", 0.0), reverse=True)
        existing = existing[:MAX_SKILLS]

    return existing


def _validate_lesson(lesson):
    required_keys = {"id", "kind", "pattern", "guidance", "confidence"}
    valid_kinds = {"intent_mapping", "constraint", "failure_pattern", "scope_hint"}
    if not isinstance(lesson, dict):
        return False
    if not required_keys.issubset(lesson.keys()):
        return False
    if lesson.get("kind") not in valid_kinds:
        return False
    confidence = lesson.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        return False
    if not isinstance(lesson.get("id"), str) or not lesson["id"]:
        return False
    return True


def main():
    digests = _read_recent_digests()
    cron_tail = _read_cron_tail()

    if not digests and not cron_tail:
        # Nothing to reflect on — silent no-op
        sys.exit(0)

    prompt = _build_prompt(digests, cron_tail)
    new_lessons = _run_claude(prompt)

    if new_lessons is None:
        # Claude failed or returned bad JSON — no-op, do not corrupt skills.json
        sys.exit(0)

    if not isinstance(new_lessons, list):
        sys.exit(0)

    # Validate each lesson; drop invalid ones
    valid_lessons = [l for l in new_lessons if _validate_lesson(l)]

    if not valid_lessons:
        sys.exit(0)

    existing = _load_skills()
    merged = _merge_skills(existing, valid_lessons)
    _save_skills(merged)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] skill_compiler: added/updated {len(valid_lessons)} lesson(s). Total: {len(merged)}.")
    sys.exit(0)


if __name__ == "__main__":
    main()
