#!/usr/bin/env python3
"""Compose and push the morning org brief.

`compose_brief` is PURE: it reads the day's pod dailies, the spend ledger, and the
decision ledger, and returns a fixed brief string. It performs no network I/O and
never raises on missing/bad input — it degrades to a partial brief. `push_brief`
sends it to Telegram.
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import decision_ledger as _dl          # noqa: E402
import cost_governor as _cg            # noqa: E402

ENV_PATH = Path.home() / ".prytan.env"


def _project_name(root: Path) -> str:
    """Read project name from .prytan.env PROJECT_NAME, fallback to dir name."""
    env_file = root.parent / ".prytan.env" if not (root / ".prytan.env").exists() else root / ".prytan.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("PROJECT_NAME="):
                return line.split("=", 1)[1].strip()
    return root.name


def _daily_path(now: datetime, root: Path, pod: str) -> Path:
    return root / ".agent-inbox" / "pods" / f"{now.strftime('%Y-%m-%d')}-{pod}-daily.md"


def _active_pods(root: Path) -> list[str]:
    """Read pod names from .agent-config/pods.yaml if it exists, else scan pod dirs."""
    cfg = root / ".agent-config" / "pods.yaml"
    if cfg.exists():
        try:
            import re
            names = re.findall(r"^  - name:\s*(\S+)", cfg.read_text(), re.MULTILINE)
            if names:
                return names
        except Exception:
            pass
    # Fallback: any pod that has run today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pods_dir = root / ".agent-inbox" / "pods"
    if pods_dir.exists():
        seen = set()
        for f in pods_dir.glob(f"{today}-*-daily.md"):
            parts = f.stem.split("-", 4)
            if len(parts) >= 4:
                seen.add(parts[3])
        if seen:
            return sorted(seen)
    return []


def _day_usd(now: datetime, root: Path) -> float:
    """Sum est_usd over usage-ledger rows dated today's calendar day."""
    d = now.strftime("%Y-%m-%d")
    total = 0.0
    p = root / ".agent-inbox" / "usage-ledger.tsv"
    try:
        for line in p.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 5 and parts[0].startswith(d):
                try:
                    total += float(parts[4])
                except ValueError:
                    continue
    except OSError:
        return 0.0
    return total


def _spend_line(now: datetime, root: Path) -> str:
    usd = _day_usd(now, root)
    budget = _cg.load_budget(root / ".agent-config" / "budget.yaml")
    mtd = _cg.mtd_spend(now, root / ".agent-inbox" / "usage-ledger.tsv")
    cap = budget.monthly_token_cap
    pct = (mtd * 100 // cap) if cap else 0
    line = f"Spend: ${usd:.2f} today · {mtd/1_000_000:.0f}M/{cap/1_000_000:.0f}M MTD"
    if cap and pct >= budget.soft_throttle_pct:
        line += f" ⚠️ {pct}% — throttling on"
    return line


def _pods_line(now: datetime, root: Path, pods: list[str]) -> str:
    marks = []
    for pod in pods:
        ok = _daily_path(now, root, pod).is_file()
        marks.append(f"{pod.capitalize()} {'✅' if ok else '⏭️ no run'}")
    return ("Pods: " + " · ".join(marks)) if marks else "No pods configured."


def _blockers(now: datetime, root: Path, pods: list[str]) -> list[tuple[str, str]]:
    """Parse each present daily's `## Blockers` section."""
    out = []
    for pod in pods:
        p = _daily_path(now, root, pod)
        try:
            lines = p.read_text().splitlines()
        except OSError:
            continue
        grab, collected = False, []
        for ln in lines:
            s = ln.strip()
            if s.lower().lstrip("#").strip().startswith("blockers"):
                grab = True
                continue
            if grab and s.startswith("#"):
                break
            if grab and s:
                collected.append(s.lstrip("-*0123456789. ").strip())
        text = " ".join(c for c in collected if c).strip()
        if text and not text.lower().startswith("none"):
            out.append((pod, text))
    return out


def compose_brief(now: datetime, root: Path = ROOT) -> str:
    pods = _active_pods(root)
    led = root / ".agent-inbox" / "decisions.jsonl"
    any_daily = any(_daily_path(now, root, p).is_file() for p in pods)
    name = _project_name(root)

    parts = []
    parts.append(f"🌅 {name} — {now.strftime('%a %d %b')}")
    if pods and not any_daily:
        parts.append("⚠️ Pods did not run today — brief built from stale state.")
    parts.append(_spend_line(now, root))
    parts.append(_pods_line(now, root, pods))
    parts.append("")

    decided = _dl.auto_resolved_today(now, led)
    parts.append(f"✅ Decided for you ({len(decided)}) — handled autonomously")
    for r in decided[:5]:
        parts.append(f"  · {r.get('title', '(untitled)')}")
    if len(decided) > 5:
        parts.append(f"  · +{len(decided) - 5} more")
    parts.append("")

    pending = _dl.pending_for_human(now, led)
    if not pending:
        parts.append("🔵 NEEDS YOU — ✅ Nothing needs you today")
    else:
        parts.append(f"🔵 NEEDS YOU ({len(pending)}) — reply with the number")
        for i, r in enumerate(pending, 1):
            age = r.get("age_days", 0)
            rec = r.get("recommendation", "")
            tail = f" — rec: {rec}" if rec else ""
            parts.append(
                f"  {i}. [{r.get('door_type','?')}][Day {age}] {r.get('title','(untitled)')}{tail}")
    parts.append("")

    blockers = _blockers(now, root, pods)
    if blockers:
        parts.append(f"⛔ Blocked ({len(blockers)})")
        for pod, text in blockers:
            parts.append(f"  · {pod}: {text[:160]}")

    return "\n".join(parts).rstrip() + "\n"


_TG_API = "https://api.telegram.org/bot{token}/sendMessage"


def _tg_send(token: str, chat_id: str, text: str) -> None:
    for i in range(0, len(text) or 1, 3900):
        chunk = text[i:i + 3900] or "(empty)"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": chunk}).encode()
        req = urllib.request.Request(_TG_API.format(token=token), data=data)
        urllib.request.urlopen(req, timeout=30).close()


def push_brief(now: datetime, root: Path = ROOT, sender=None, env_path: Path = ENV_PATH) -> bool:
    """Compose the brief and send it to Telegram. Falls back to a file on any error."""
    brief = compose_brief(now, root)
    fallback = root / ".agent-inbox" / f"{now.strftime('%Y-%m-%d')}-brief.md"

    def _fallback() -> bool:
        try:
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text(brief)
        except OSError:
            pass
        return False

    def _load_env(path: Path) -> dict:
        env = {}
        if not path.exists():
            return env
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
        return env

    try:
        if sender is None:
            sender = _tg_send
        env = _load_env(env_path)
        token = env.get("TELEGRAM_BOT_TOKEN")
        chat = env.get("ALLOWED_CHAT_ID")
        if not token or not chat:
            return _fallback()
        sender(token, chat, brief)
        return True
    except Exception:
        return _fallback()


if __name__ == "__main__":            # pragma: no cover
    ok = push_brief(datetime.now(timezone.utc))
    print(f"[morning_brief] pushed={ok}")
