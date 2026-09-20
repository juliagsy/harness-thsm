#!/usr/bin/env python3
"""Convert paper/draft.md into the LaTeX sources under paper/sections/.

The markdown draft stays the source of truth: every number in it is produced by
`decaymem.report` from the experiment directories. This script is the deterministic
last mile, so regenerating the paper after new runs is `make tex && make pdf`.

Handles: headings, emphasis, inline code, bullet and numbered lists, pipe tables
(booktabs), figures with italic captions, author-year citations against
scripts/citemap.json, and the unicode the draft uses for numbers and arrows.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRAFT = ROOT / "draft.md"
OUT = ROOT / "sections"
CITEMAP = json.loads((ROOT / "scripts" / "citemap.json").read_text())

UNICODE = [
    ("±", r"$\pm$"), ("×", r"$\times$"), ("≈", r"$\approx$"), ("≥", r"$\geq$"),
    ("≤", r"$\leq$"), ("→", r"$\rightarrow$"), ("←", r"$\leftarrow$"), ("⊆", r"$\subseteq$"),
    ("∈", r"$\in$"), ("−", "-"), ("–", "--"), ("—", "---"), ("…", r"\ldots{}"),
    ("“", "``"), ("”", "''"), ("‘", "`"), ("’", "'"), ("£", r"\pounds{}"),
    ("τ", r"$\tau$"), ("ℓ", r"$\ell$"), ("π", r"$\pi$"), ("σ", r"$\sigma$"),
    ("⟨", r"$\langle$"), ("⟩", r"$\rangle$"), ("·", r"$\cdot$"), ("§", r"\S"),
]
ESCAPES = [("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"),
           ("$", r"\$"), ("{", r"\{"), ("}", r"\}")]

# "Surname 2026", "Surname et al. 2026", "Surname and Other 1991", joined by "; "
_ONE = r"[A-Z][\w'\u2019.-]+(?: et al\.| and [A-Z][\w'\u2019.-]+)? \d{4}"
CITE_RE = re.compile(rf"[\[(]({_ONE}(?:; ?{_ONE})*)[\])]")


def _protect(text: str) -> tuple[str, list[str]]:
    """Pull `code` spans out before escaping, so their contents survive verbatim."""
    spans: list[str] = []

    def take(m: re.Match) -> str:
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    return re.sub(r"`([^`]+)`", take, text), spans


def _restore(text: str, spans: list[str]) -> str:
    def put(m: re.Match) -> str:
        body = spans[int(m.group(1))]
        for a, b in ESCAPES + [("{", r"\{"), ("}", r"\}"), ("^", r"\^{}"), ("~", r"\~{}")]:
            body = body.replace(a, b)
        return r"\texttt{" + body + "}"

    return re.sub("\x00(\\d+)\x00", put, text)


def _cite(text: str) -> str:
    def sub(m: re.Match) -> str:
        keys = []
        for part in m.group(1).split(";"):
            k = CITEMAP.get(part.strip())
            if k is None:
                return m.group(0)  # not a citation we know: leave the prose alone
            keys.append(k)
        return "\x01citep\x02" + ",".join(keys) + "\x03"

    return CITE_RE.sub(sub, text)


def inline(text: str) -> str:
    text, spans = _protect(text)
    text = _cite(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)  # md links -> plain text
    text = re.sub(r'"([^"]+)"', r"``\1''", text)  # straight quotes -> TeX quotes
    # "Table 2" / "Table C1" / "Figure 3" -> real cross-references
    text = re.sub(r"\bTable (C?\d+)\b", "Table~\x01ref\x02tab:\\1\x03", text)
    text = re.sub(r"\bFigure (\d+)\b", "Figure~\x01ref\x02fig:\\1\x03", text)
    # emphasis first, as markers rather than braces, so literal braces can be escaped after
    text = re.sub(r"\*\*(.+?)\*\*", "\x01textbf\x02\\1\x03", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", "\x01emph\x02\\1\x03", text)
    for a, b in ESCAPES:
        text = text.replace(a, b)
    for a, b in UNICODE:
        text = text.replace(a, b)
    text = text.replace("\x01", "\\").replace("\x02", "{").replace("\x03", "}")
    return _restore(text, spans)


def table(rows: list[str], caption: str, number: str | None) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    header, body = cells[0], cells[2:]
    n = len(header)

    def numericish(col: int) -> bool:
        vals = [r[col] for r in body if col < len(r) and r[col] not in ("", "-")]
        if not vals:
            return False
        hits = sum(bool(re.match(r"^[\d.$%+-]", v.lstrip("*"))) for v in vals)
        return hits >= 0.6 * len(vals)

    # right-align columns that hold numbers, left-align the ones that hold words
    align = "".join("r" if numericish(i) else "l" for i in range(n))
    size = r"\footnotesize" if n > 5 else r"\small"
    head: list[str] = []
    if number is None:  # no caption in the draft: keep it inline and unnumbered
        head = [r"\begin{center}", size, r"\begin{adjustbox}{max width=\linewidth}"]
        tail = [r"\end{adjustbox}", r"\end{center}", ""]
    else:
        pre = []
        if number[0].isalpha():  # appendix table: number it C1, C2, ...
            pre = [r"\setcounter{table}{0}",
                   r"\renewcommand{\thetable}{" + number[0] + r"\arabic{table}}"]
        head = pre + [r"\begin{table}[t]", r"\centering", size,
                      r"\caption{" + inline(caption) + "}", r"\label{tab:" + number + "}",
                      r"\begin{adjustbox}{max width=\linewidth}"]
        tail = [r"\end{adjustbox}", r"\end{table}", ""]
    out = head + [
           r"\begin{tabular}{" + align + "}", r"\toprule",
           " & ".join(inline(c) for c in header) + r" \\", r"\midrule"]
    for row in body:
        row = (row + [""] * n)[:n]
        out.append(" & ".join(inline(c) for c in row) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"] + tail
    return "\n".join(out)


def convert(md: str) -> tuple[str, dict[str, str]]:
    """Return (abstract, {section-file-stem: latex})."""
    lines = md.splitlines()
    sections: dict[str, list[str]] = {}
    abstract: list[str] = []
    cur: list[str] | None = None
    stem = ""
    in_appendix = False
    i = 0
    tbl_n = fig_n = 0
    pending_caption: str | None = None

    def flush_para(buf: list[str], out: list[str]) -> None:
        if buf:
            out.append(inline(" ".join(buf)))
            out.append("")
            buf.clear()

    para: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        m = re.match(r"^## (.+)$", line)
        if m:
            flush_para(para, cur if cur is not None else abstract)
            title = m.group(1)
            if title.lower().startswith("references"):
                cur = None  # bibliography replaces it
                while i < len(lines) and not lines[i].startswith("## Appendix"):
                    i += 1
                continue
            if title.lower() == "abstract":
                cur, stem = abstract, "abstract"
                i += 1
                continue
            body = re.sub(r"^\d+\.\s*", "", title)
            if title.startswith("Appendix"):
                body = re.sub(r"^Appendix [A-Z]\.\s*", "", title)
                if not in_appendix:
                    in_appendix = True
            stem = re.sub(r"[^a-z0-9]+", "-", body.lower()).strip("-")[:28]
            sections[stem] = [(r"\appendix" + "\n" if in_appendix and
                               len([k for k in sections if k]) and
                               not any("\\appendix" in "\n".join(v) for v in sections.values())
                               else "") + r"\section{" + inline(body) + "}",
                              r"\label{sec:" + stem + "}", ""]
            cur = sections[stem]
            i += 1
            continue

        m = re.match(r"^### (.+)$", line)
        if m and cur is not None:
            flush_para(para, cur)
            body = re.sub(r"^\d+\.\d+\s*", "", m.group(1))
            cur += [r"\subsection{" + inline(body) + "}", ""]
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        # figure: ![](path) optionally followed by an italic caption line
        m = re.match(r"^!\[\]\((.+?)\)\s*$", stripped)
        if m:
            flush_para(para, cur)
            path = m.group(1).replace("figures/", "").rsplit(".", 1)[0]
            cap = ""
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith("*"):
                capbuf = []
                while j < len(lines) and lines[j].strip():
                    capbuf.append(lines[j].strip())
                    j += 1
                cap = " ".join(capbuf).strip("*")
                i = j
            fig_n += 1
            num = re.match(r"^Figure (\d+)\.", cap)
            cap = re.sub(r"^Figure \d+\.\s*", "", cap)
            cur += [r"\begin{figure}[t]", r"\centering",
                    r"\includegraphics[width=\linewidth]{figures/" + path + "}",
                    r"\caption{" + inline(cap) + "}",
                    r"\label{fig:" + (num.group(1) if num else str(fig_n)) + "}",
                    r"\end{figure}", ""]
            i += 1
            continue

        # table caption line ("Table N. ...") then a pipe table
        if re.match(r"^Table [\w.]+\.", stripped):
            capbuf = [stripped]
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].lstrip().startswith("|"):
                capbuf.append(lines[j].strip())
                j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("|"):
                flush_para(para, cur)
                rows = []
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    rows.append(lines[j])
                    j += 1
                cap = " ".join(capbuf)
                num = re.match(r"^Table (C?\d+)\.", cap)
                cap = re.sub(r"^Table [\w.]+\.\s*", "", cap)
                cur.append(table(rows, cap, num.group(1) if num else None))
                i = j
                continue
            pending_caption = " ".join(capbuf)
            i = j
            continue

        # bare pipe table (no explicit caption line)
        if stripped.startswith("|"):
            flush_para(para, cur)
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            cap = pending_caption or ""
            num = re.match(r"^Table (C?\d+)\.", cap)
            cap = re.sub(r"^Table [\w.]+\.\s*", "", cap)
            pending_caption = None
            cur.append(table(rows, cap, num.group(1) if num else None))
            continue

        # lists
        if re.match(r"^[-*] ", stripped) or re.match(r"^\d+\. ", stripped):
            flush_para(para, cur)
            ordered = bool(re.match(r"^\d+\. ", stripped))
            env = "enumerate" if ordered else "itemize"
            cur.append(r"\begin{" + env + "}")
            while i < len(lines):
                s = lines[i].strip()
                if re.match(r"^[-*] ", s) or re.match(r"^\d+\. ", s):
                    item = re.sub(r"^(?:[-*]|\d+\.)\s+", "", s)
                    j = i + 1
                    while (j < len(lines) and lines[j].strip()
                           and not re.match(r"^[-*] |^\d+\. ", lines[j].strip())
                           and lines[j].startswith(("  ", "\t"))):
                        item += " " + lines[j].strip()
                        j += 1
                    cur.append(r"\item " + inline(item))
                    i = j
                elif not s:
                    if i + 1 < len(lines) and re.match(r"^[-*] |^\d+\. ", lines[i + 1].strip()):
                        i += 1
                    else:
                        break
                else:
                    break
            cur.append(r"\end{" + env + "}")
            cur.append("")
            continue

        # code block
        if stripped.startswith("```") or (line.startswith("    ") and not para):
            flush_para(para, cur)
            if stripped.startswith("```"):
                i += 1
                buf = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    buf.append(lines[i])
                    i += 1
                i += 1
            else:
                buf = []
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    buf.append(lines[i][4:] if lines[i].startswith("    ") else "")
                    i += 1
                while buf and not buf[-1].strip():
                    buf.pop()
            cur += [r"\begin{Verbatim}[breaklines=true,breakanywhere=true,fontsize=\small,xleftmargin=1em]"] + buf + [r"\end{Verbatim}", ""]
            continue

        if not stripped:
            flush_para(para, cur)
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush_para(para, cur if cur is not None else abstract)
    abstract_tex = "\n".join(x for x in abstract if x.strip())
    return abstract_tex, {k: "\n".join(v).rstrip() + "\n" for k, v in sections.items()}


def main() -> int:
    md = DRAFT.read_text()
    md = md.split("\n", 1)[1] if md.startswith("# ") else md
    md = re.sub(r"^\*Draft v.*?\*\s*$", "", md, flags=re.M | re.S, count=1)
    abstract, sections = convert(md)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.tex"):
        f.unlink()
    (OUT / "00-abstract.tex").write_text(abstract + "\n")
    order = []
    for n, (stem, tex) in enumerate(sections.items(), start=1):
        name = f"{n:02d}-{stem}.tex"
        (OUT / name).write_text(tex)
        order.append(name)
    (ROOT / "scripts" / "order.json").write_text(json.dumps(order, indent=1))
    print(f"wrote {len(order)} sections + abstract to {OUT}")
    for name in order:
        print("  ", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
