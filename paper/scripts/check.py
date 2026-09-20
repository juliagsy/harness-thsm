#!/usr/bin/env python3
"""Fail the build on the problems that matter for a preprint: undefined citations or
references, overfull boxes past a threshold, and leftover fill-me placeholders."""

from __future__ import annotations

import pathlib
import re
import sys

OVERFULL_PT = 5.0


def main(log_path: str = "build/main.log") -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    log = (root / log_path).read_text(errors="replace")
    problems: list[str] = []

    # LaTeX Warning: Citation `foo' on page 3 undefined   /   Reference `bar' ... undefined
    for kind, name in re.findall(r"(Citation|Reference) `([^']+)' [^\n]*undefined", log):
        problems.append(f"undefined {kind.lower()}: {name}")

    for pt, lines in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\)[^\n]*?lines (\d+--\d+)",
                                log):
        if float(pt) > OVERFULL_PT:
            problems.append(f"overfull hbox {pt}pt at lines {lines}")

    tex = "\n".join(p.read_text() for p in (root / "sections").glob("*.tex"))
    tex += (root / "main.tex").read_text()
    for marker in ("[SURNAME]", "[to be filled]", "TODO", "example.com"):
        if marker in tex:
            problems.append(f"placeholder still present: {marker}")

    if problems:
        print("check FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    pages = re.search(r"\((\d+) pages", log)
    print(f"check passed ({pages.group(1) if pages else '?'} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
