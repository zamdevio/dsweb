#!/usr/bin/env python3
"""CLI SSE filter: stdin DeepSeek SSE → assistant text on stdout.

Uses client.sse. Set DS_SHOW_THINK=1 to also emit THINK fragments.
"""
from __future__ import annotations

import os
import sys
import pathlib

LIB = pathlib.Path(__file__).resolve().parent
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from client.sse import iter_events  # noqa: E402


def main() -> int:
    show_think = os.environ.get("DS_SHOW_THINK", "").lower() in (
        "1", "true", "yes", "on",
    )
    printed = False
    for kind, text in iter_events(sys.stdin):
        if kind == "reasoning" and not show_think:
            continue
        sys.stdout.write(text)
        sys.stdout.flush()
        printed = True
    if printed:
        sys.stdout.write("\n")
    # Drain so upstream curl doesn't SIGPIPE when we stop early.
    try:
        sys.stdin.read()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
