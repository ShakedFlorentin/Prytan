from __future__ import annotations
import sys
from pathlib import Path
from core import onboarding as ob


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: onboarding <scan DIR... | install-agent ID | "
              "config-set KEY VALUE | wire-hook>", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    cwd = Path.cwd()
    if cmd == "scan":
        if not rest:
            print("scan: need at least one dir", file=sys.stderr); return 2
        # Pull optional --books <dir> from the argument list
        books_dir = None
        filtered_rest = []
        i = 0
        while i < len(rest):
            if rest[i] == "--books" and i + 1 < len(rest):
                books_dir = rest[i + 1]
                i += 2
            else:
                filtered_rest.append(rest[i])
                i += 1
        if not filtered_rest:
            print("scan: need at least one source dir", file=sys.stderr); return 2
        out = ob.scan_sources(cwd, filtered_rest, books_dir=books_dir)
        print(f"scanned {filtered_rest} -> {out}")
        return 0
    if cmd == "install-agent":
        for aid in rest:
            ob.install_agent(cwd, aid)
        print(f"installed: {', '.join(rest)}")
        return 0
    if cmd == "config-set":
        if len(rest) != 2:
            print("config-set: need KEY VALUE", file=sys.stderr); return 2
        ob.config_set(cwd, rest[0], rest[1])
        print(f"set {rest[0]} = {rest[1]}")
        return 0
    if cmd == "wire-hook":
        ob.wire_hook(cwd)
        print("hook wired")
        return 0
    if cmd == "author-agent":
        # Pull optional --role-type (authoring|advisory) from the argument list
        role_type = "authoring"
        filtered_rest = []
        i = 0
        while i < len(rest):
            if rest[i] == "--role-type" and i + 1 < len(rest):
                role_type = rest[i + 1]
                i += 2
            else:
                filtered_rest.append(rest[i])
                i += 1
        if len(filtered_rest) < 3:
            print("author-agent: need ID NAME DESCRIPTION (body on stdin)", file=sys.stderr)
            return 2
        body = sys.stdin.read()
        ob.author_agent(cwd, filtered_rest[0], filtered_rest[1], filtered_rest[2],
                        body, role_type=role_type)
        print(f"authored agent: {filtered_rest[0]} (role_type={role_type})")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
