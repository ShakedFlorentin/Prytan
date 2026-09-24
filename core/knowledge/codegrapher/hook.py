#!/usr/bin/env python3
"""PreToolUse hook: a soft reminder to query the code graph before broad searches.
Reads the Claude Code hook payload on stdin, prints a one-line reminder to stderr,
and exits 0 (non-blocking). Enforcement strictness can grow later."""
import sys


def main() -> int:
    sys.stdin.read()   # drain payload; non-blocking reminder only
    print("[codegrapher] tip: `python3 -m core.knowledge.codegrapher query <term>` "
          "to locate code before a broad search.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
