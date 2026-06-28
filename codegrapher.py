#!/usr/bin/env python3
"""
codegrapher.py — entry point.

Delegates to codegrapher.cli.main().

Usage:
    python3 codegrapher.py scan <directory>
    python3 codegrapher.py query "<topic>"
    python3 codegrapher.py explain "<symbol>"
    python3 codegrapher.py path "<a>" "<b>"
    python3 codegrapher.py stats
"""

from codegrapher.cli import main

if __name__ == "__main__":
    main()
