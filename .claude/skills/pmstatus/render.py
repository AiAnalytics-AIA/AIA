#!/usr/bin/env python3
"""Render the AIA PM status JSON as one self-contained HTML page.

Usage: python3 render.py status.json out.html

Stdlib only. Every string from the JSON is escaped: session text is untrusted.
"""

# ruff: noqa: E501 -- the page's CSS, HTML and script are template strings, kept one rule per line.
from __future__ import annotations

import json
import sys
from datetime import datetime
from html import escape

STATES = {
    "working": ("Working", "active"),
    "waiting-on-nigel": ("Needs you", "you"),
    "waiting-on-review": ("Waiting on review", "review"),
    "waiting-on-other-session": ("Waiting on session", "waiting"),
    "done": ("Done", "done"),
    "blocked": ("Blocked", "blocked"),
}
STEP_STATUS = {
    "done": "Done",
    "active": "Active",
    "waiting": "Waiting",
    "blocked": "Blocked",
    "todo": "To do",
}
CI = {"green": "ok", "red": "bad", "pending": "pend", "none": "none"}
CATEGORY_ORDER = ["PM", "Planning", "Scope inputs", "Infra", "Security/CI", "Docs", "Design"]


def e(value: object) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def short_time(value: object) -> str:
    if not value:
        return ""
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M UTC")
    except ValueError:
        return text


def num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- graph


def label_index(data: dict) -> dict[str, str]:
    """Every referenceable id -> a short human label."""
    labels: dict[str, str] = {}
    for n in as_list(data.get("needs_nigel")):
        if isinstance(n, dict) and n.get("id"):
            labels[str(n["id"])] = str(n.get("title") or n["id"])
    for w in as_list(data.get("workstreams")):
        if not isinstance(w, dict):
            continue
        for s in as_list(w.get("steps")):
            if isinstance(s, dict) and s.get("id"):
                labels[str(s["id"])] = str(s.get("title") or s["id"])
    for a in as_list(data.get("next_actions")):
        if isinstance(a, dict) and a.get("id"):
            labels[str(a["id"])] = str(a.get("what") or a["id"])
    for s in as_list(data.get("sessions")):
        if isinstance(s, dict) and s.get("id"):
            labels[str(s["id"])] = str(s.get("title") or s["id"])
    return labels


def dependents(data: dict) -> dict[str, set[str]]:
    """id -> the ids that directly wait on it."""
    out: dict[str, set[str]] = {}
    for w in as_list(data.get("workstreams")):
        if not isinstance(w, dict):
            continue
        for s in as_list(w.get("steps")):
            if not isinstance(s, dict) or not s.get("id"):
                continue
            for d in as_list(s.get("depends_on")):
                out.setdefault(str(d), set()).add(str(s["id"]))
    for a in as_list(data.get("next_actions")):
        if isinstance(a, dict) and a.get("id"):
            for d in as_list(a.get("after")):
                out.setdefault(str(d), set()).add(str(a["id"]))
    for n in as_list(data.get("needs_nigel")):
        if isinstance(n, dict) and n.get("id"):
            for u in as_list(n.get("unblocks")):
                out.setdefault(str(n["id"]), set()).add(str(u))
    return out


def reach(start: list, graph: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [str(x) for x in start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur, ()))
    return seen


def chip(ref: str, labels: dict[str, str], cls: str = "chip") -> str:
    label = labels.get(ref)
    title = f' title="{e(label)}"' if label else ""
    text = e(label if label and len(label) <= 34 else (label[:32] + "…" if label else ref))
    return f'<span class="{cls}"{title}><b>{e(ref)}</b> {text if label else ""}</span>'


# ---------------------------------------------------------------- svg chain


def wrap(text: str, width: int, lines: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) <= width:
            cur = cand
            continue
        if cur:
            out.append(cur)
        cur = w if len(w) <= width else w[: width - 1] + "…"
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
    joined = " ".join(out)
    if len(joined) < len(" ".join(words)) and out:
        last = out[-1]
        out[-1] = (last[: width - 1] + "…") if len(last) >= width else last + "…"
    return out


def chain_svg(ws: dict, labels: dict[str, str]) -> str:
    steps = [s for s in as_list(ws.get("steps")) if isinstance(s, dict)]
    if not steps:
        return '<p class="muted">No steps.</p>'
    box_w, box_h, gap = 150, 64, 34
    pos = {str(s.get("id")): i for i, s in enumerate(steps)}
    has_arc = any(
        str(d) in pos and pos[str(d)] != i - 1
        for i, s in enumerate(steps)
        for d in as_list(s.get("depends_on"))
    )
    top = 46 if has_arc else 16
    width = len(steps) * box_w + (len(steps) - 1) * gap + 16
    has_ext = any(str(d) not in pos for s in steps for d in as_list(s.get("depends_on")))
    height = top + box_h + (28 if has_ext else 8)
    parts: list[str] = []
    x_of = lambda i: 8 + i * (box_w + gap)  # noqa: E731
    # arrows first so nodes draw over them
    arcs = 0
    externals: dict[int, list[str]] = {}
    for i, s in enumerate(steps):
        for d in as_list(s.get("depends_on")):
            d = str(d)
            if d not in pos:
                externals.setdefault(i, []).append(d)
                continue
            j = pos[d]
            if j == i - 1:
                x1, x2, y = x_of(j) + box_w, x_of(i) - 2, top + box_h / 2
                parts.append(
                    f'<path class="arr" d="M{x1:.0f},{y:.0f} L{x2:.0f},{y:.0f}" marker-end="url(#ah)"/>'
                )
            else:
                arcs += 1
                x1, x2 = x_of(j) + box_w / 2, x_of(i) + box_w / 2
                lift = 14 + 8 * (arcs % 3)
                parts.append(
                    f'<path class="arr" d="M{x1:.0f},{top} C{x1:.0f},{top - lift - 10} {x2:.0f},'
                    f'{top - lift - 10} {x2:.0f},{top - 2}" marker-end="url(#ah)"/>'
                )
    for i, s in enumerate(steps):
        status = str(s.get("status") or "todo")
        if status not in STEP_STATUS:
            status = "todo"
        x = x_of(i)
        title_full = str(s.get("title") or s.get("id") or "")
        tip = f"{s.get('id', '')}: {title_full} - {STEP_STATUS[status]}; owner {s.get('owner') or 'unknown'}"
        parts.append(f'<g class="node st-{status}"><title>{e(tip)}</title>')
        parts.append(f'<rect x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="10"/>')
        lines = wrap(title_full, 16, 2)
        for k, line in enumerate(lines):
            parts.append(f'<text class="nt" x="{x + 10}" y="{top + 20 + k * 16}">{e(line)}</text>')
        owner = wrap(str(s.get("owner") or ""), 22, 1)
        if owner:
            parts.append(
                f'<text class="no" x="{x + 10}" y="{top + box_h - 9}">{e(owner[0])}</text>'
            )
        if status == "blocked":
            cx, cy = x + box_w - 4, top + 4
            parts.append(f'<circle class="bdg" cx="{cx}" cy="{cy}" r="10"/>')
            parts.append(f'<text class="bdgt" x="{cx}" y="{cy + 4}" text-anchor="middle">!</text>')
        elif status == "done":
            cx, cy = x + box_w - 4, top + 4
            parts.append(f'<circle class="bdg-ok" cx="{cx}" cy="{cy}" r="9"/>')
            parts.append(f'<path class="tick" d="M{cx - 4},{cy} l3,3 l5,-6"/>')
        parts.append("</g>")
        ext = externals.get(i)
        if ext:
            txt = "after " + ", ".join(ext)
            full = "; ".join(f"{d}: {labels.get(d, d)}" for d in ext)
            parts.append(
                f'<text class="ext" x="{x + 2}" y="{top + box_h + 18}"><title>{e(full)}</title>↳ {e(wrap(txt, 26, 1)[0])}</text>'
            )
    defs = (
        '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path class="ahp" d="M0,0 L10,5 L0,10 z"/></marker></defs>'
    )
    return (
        ('<div class="hint">scroll →</div>' if len(steps) > 2 else "")
        + f'<div class="chain"><svg role="img" aria-label="{e(ws.get("title"))} step chain" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">{defs}{"".join(parts)}</svg></div>'
    )


# ---------------------------------------------------------------- pieces


def gauge(pct: float | None) -> str:
    if pct is None:
        return '<div class="gauge g-unk" title="Context usage unknown"><svg viewBox="0 0 36 36"><circle class="gt" cx="18" cy="18" r="15"/></svg><span>?</span></div>'
    p = max(0.0, min(100.0, pct))
    cls = "g-red" if p >= 70 else "g-amber" if p >= 60 else "g-ok"
    circ = 2 * 3.14159 * 15
    dash = circ * p / 100
    return (
        f'<div class="gauge {cls}" title="Context used: {p:.0f}%"><svg viewBox="0 0 36 36">'
        f'<circle class="gt" cx="18" cy="18" r="15"/>'
        f'<circle class="gv" cx="18" cy="18" r="15" stroke-dasharray="{dash:.1f} {circ:.1f}" transform="rotate(-90 18 18)"/>'
        f"</svg><span>{p:.0f}%</span></div>"
    )


def progress(plan: dict | None) -> str:
    if not isinstance(plan, dict):
        return '<div class="plan muted">No plan file named.</div>'
    done, total = num(plan.get("done")), num(plan.get("total"))
    bar = ""
    if done is not None and total:
        pct = max(0.0, min(100.0, 100 * done / total))
        bar = (
            f'<div class="bar" role="img" aria-label="{done:.0f} of {total:.0f} chunks"><i style="width:{pct:.1f}%"></i></div>'
            f'<span class="frac">{done:.0f}/{total:.0f}</span>'
        )
    else:
        bar = '<span class="frac muted">chunks unknown</span>'
    return (
        f'<div class="plan"><div class="planpath">{e(plan.get("path"))}</div>'
        f'<div class="barrow">{bar}</div>'
        f'<div class="chunk"><span class="k">Chunk</span> {e(plan.get("chunk")) or "<span class=muted>unknown</span>"}</div></div>'
    )


def pr_chips(prs: list) -> str:
    out = []
    for p in prs:
        if not isinstance(p, dict):
            continue
        ci = CI.get(str(p.get("ci") or "none"), "none")
        state = str(p.get("state") or "")
        tip = f"#{p.get('num')} {p.get('title') or ''} - {state}, CI {p.get('ci') or 'none'}"
        out.append(
            f'<span class="pr ci-{ci}" title="{e(tip)}"><i></i>#{e(p.get("num"))}'
            f"<small>{e(state)}</small></span>"
        )
    return f'<div class="prs">{"".join(out)}</div>' if out else ""


def safe_url(value: object) -> str | None:
    text = str(value or "").strip()
    return text if text.lower().startswith(("https://", "http://")) else None


def explainer_row(items: list) -> str:
    """Each explainer embedded in a sandboxed srcdoc iframe (scripts only, no same-origin:
    the untrusted code cannot reach this page or its db); a link when no html was fetched."""
    out = []
    for x in items:
        if not isinstance(x, dict) or not x.get("title"):
            continue
        url = safe_url(x.get("source_url") or x.get("url"))
        title = str(x.get("title"))
        fn = f" — {e(x.get('function'))}" if x.get("function") else ""
        link = (
            f' <a href="{e(url)}" target="_blank" rel="noopener noreferrer">Open full size</a>'
            if url
            else ""
        )
        html_src = x.get("html")
        h = num(x.get("height"))
        height = int(max(160, min(900, h))) if h is not None else 360
        if isinstance(html_src, str) and html_src.strip():
            out.append(
                f'<figure class="explf"><iframe sandbox="allow-scripts" srcdoc="{escape(html_src, quote=True)}" '
                f'title="{e(title)}" loading="lazy" referrerpolicy="no-referrer" style="--h:{height}px"></iframe>'
                f"<figcaption>▶ {e(title)}{fn}{link}</figcaption></figure>"
            )
        elif url:
            out.append(
                f'<a class="expl" href="{e(url)}" target="_blank" rel="noopener noreferrer">▶ Explainer: {e(title)}'
                f"<small>{fn}</small></a>"
            )
        else:
            out.append(
                f'<span class="expl">▶ Explainer: {e(title)}<small>{fn} (no link)</small></span>'
            )
    return f'<div class="expls">{"".join(out)}</div>' if out else ""


def session_card(s: dict, labels: dict[str, str]) -> str:
    state = str(s.get("state") or "")
    label, cls = STATES.get(state, (state or "Unknown", "waiting"))
    reply = str(s.get("reply") or "")
    noreply = (
        '<span class="noreply" title="No reply to the status request; filled from its session summary">no reply</span>'
        if reply == "no reply"
        else ""
    )

    def field(k: str, body: str, extra: str = "") -> str:
        return f'<div class="fld{extra}"><div class="k">{k}</div><div>{body}</div></div>'

    col1 = []
    col1.append(field("Doing", e(s.get("doing")) or '<span class="muted">unknown</span>'))
    if s.get("next"):
        col1.append(field("Next", e(s.get("next"))))
    col2 = [field("Plan chunk", progress(s.get("plan")))]
    prs = pr_chips(as_list(s.get("prs")))
    col2.append(field("PRs", prs or '<span class="muted">none</span>'))
    col3 = []
    if s.get("needs"):
        col3.append(field("Needs you", e(s.get("needs")), " need"))
    bb = [str(x) for x in as_list(s.get("blocked_by"))]
    col3.append(
        field(
            "Blocked by",
            f'<span class="chips">{"".join(chip(x, labels) for x in bb)}</span>'
            if bb
            else '<span class="muted">nothing</span>',
        )
    )
    return (
        f'<article class="card sess s-{cls}">'
        f'<header><div class="sh"><h4>{e(s.get("title"))}</h4>'
        f'<div class="sid">{e(s.get("id"))}</div>'
        f'<div class="pills"><span class="pill p-{cls}">{e(label)}</span>{noreply}'
        f'<span class="upd muted">Updated {e(short_time(s.get("last_update"))) or "unknown"}</span></div></div>'
        f"{gauge(num(s.get('context_pct')))}</header>"
        f'<div class="sgrid"><div class="scol">{"".join(col1)}</div><div class="scol">{"".join(col2)}</div>'
        f'<div class="scol">{"".join(col3)}</div></div>'
        f"{explainer_row(as_list(s.get('explainers')))}"
        f"</article>"
    )


# ---------------------------------------------------------------- questions


def question_card(q: dict, labels: dict[str, str]) -> str:
    qid = str(q.get("id") or "")
    rec = str(q.get("rec") or "")
    tiles = []
    for o in as_list(q.get("options")):
        if not isinstance(o, dict):
            continue
        key = str(o.get("key") or "")
        is_rec = key == rec
        badge = '<span class="badge">Recommended</span>' if is_rec else ""
        detail = f'<span class="od">{e(o.get("detail"))}</span>' if o.get("detail") else ""
        tiles.append(
            f'<label class="opt{" is-rec" if is_rec else ""}"><input type="radio" name="opt-{e(qid)}" value="{e(key)}">'
            f'<span class="ob"><span class="ol"><span class="okey">{e(key)}</span>{e(o.get("label"))}{badge}</span>{detail}</span></label>'
        )
    why = (
        f'<div class="why"><div class="k">Why we recommend it</div><p>{e(q.get("rationale"))}</p></div>'
        if q.get("rationale")
        else ""
    )
    unb = "".join(chip(str(u), labels) for u in as_list(q.get("unblocks")))
    return (
        f'<article class="card qcard" data-qid="{e(qid)}">'
        f'<header class="qh"><span class="qid">{e(qid)}</span><h3>{e(q.get("title"))}</h3>'
        f'<span class="qbadge" hidden></span></header>'
        f'<div class="answered" hidden><span class="k">Answered</span><b class="alabel"></b>'
        f'<span class="anote muted"></span><button type="button" class="btn ghost change">Change</button></div>'
        f'<div class="qbody">'
        f'<p class="ctx">{e(q.get("context"))}</p>'
        + (
            f'<div class="exbox"><div class="k">Practical example</div><p>{e(q.get("example"))}</p></div>'
            if q.get("example")
            else ""
        )
        + f'<form class="qform" novalidate><fieldset><legend class="k">Your choice</legend>'
        f'<div class="opts">{"".join(tiles)}</div></fieldset>{why}'
        + (f'<div class="unb"><span class="k">unblocks →</span>{unb}</div>' if unb else "")
        + '<label class="note"><span class="k">Note (optional)</span><textarea rows="2" maxlength="4000" '
        'placeholder="Anything the session should know"></textarea></label>'
        '<div class="qact"><button type="submit" class="btn primary save" disabled>Save</button>'
        '<button type="button" class="btn ghost cancel" hidden>Cancel</button>'
        '<span class="savemsg" role="status" aria-live="polite"></span></div></form></div></article>'
    )


def decided_html(items: list) -> str:
    rows = []
    for d in items:
        if not isinstance(d, dict):
            continue
        note = f' <span class="muted">— {e(d.get("note"))}</span>' if d.get("note") else ""
        rows.append(
            f'<li><span class="qid">{e(d.get("id"))}</span><span><b>{e(d.get("title"))}</b>: '
            f"{e(d.get('choice_label') or d.get('choice'))}{note}</span>"
            f"<time>{e(short_time(d.get('at')))}</time></li>"
        )
    if not rows:
        return ""
    return f'<details class="card decided"><summary>Decided <span class="n">{len(rows)}</span></summary><ul>{"".join(rows)}</ul></details>'


def json_script(element_id: str, value: object) -> str:
    text = json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "\\u003c!--")
    return f'<script type="application/json" id="{element_id}">{text}</script>'


# ---------------------------------------------------------------- page

CSS = r"""
:root{
  --bg:#f6f7f9;--surface:#ffffff;--surface2:#f0f2f5;--ink:#15181d;--muted:#5b6370;--line:#dde1e7;
  --done:#1f8a4c;--done-bg:#e3f4ea;--active:#2563c9;--active-bg:#e3ecfb;--wait:#a86400;--wait-bg:#fdf0d9;
  --block:#c62f2f;--block-bg:#fbe4e4;--todo:#6b7380;--todo-bg:#eef0f3;--you:#b45309;--you-bg:#fff1dc;
  --review:#6d3fc0;--review-bg:#efe8fb;--accent:#d9480f;--shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.08);
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f1115;--surface:#171a20;--surface2:#1e222a;--ink:#e8eaee;--muted:#9aa3b0;--line:#2c313b;
  --done:#4cc782;--done-bg:#163525;--active:#6ea2ff;--active-bg:#18284a;--wait:#f0b452;--wait-bg:#3a2c12;
  --block:#ff6b6b;--block-bg:#421b1b;--todo:#9aa3b0;--todo-bg:#232831;--you:#ffa94d;--you-bg:#3d2810;
  --review:#b394ff;--review-bg:#2b2145;--accent:#ff8a4c;--shadow:none;}}
:root[data-theme="dark"]{
  --bg:#0f1115;--surface:#171a20;--surface2:#1e222a;--ink:#e8eaee;--muted:#9aa3b0;--line:#2c313b;
  --done:#4cc782;--done-bg:#163525;--active:#6ea2ff;--active-bg:#18284a;--wait:#f0b452;--wait-bg:#3a2c12;
  --block:#ff6b6b;--block-bg:#421b1b;--todo:#9aa3b0;--todo-bg:#232831;--you:#ffa94d;--you-bg:#3d2810;
  --review:#b394ff;--review-bg:#2b2145;--accent:#ff8a4c;--shadow:none;}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;overflow-wrap:anywhere}
main{max-width:1240px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:18px;margin:36px 0 12px;display:flex;align-items:center;gap:10px}
h2 .n{font-size:12px;font-weight:600;color:var(--muted);background:var(--surface2);border:1px solid var(--line);border-radius:999px;padding:1px 8px}
h3{font-size:15px;margin:0 0 8px}
h4{font-size:15px;margin:0}
.muted{color:var(--muted)}
.meta{color:var(--muted);font-size:13px;margin-bottom:10px}
.headline{font-size:17px;max-width:900px;margin:8px 0 18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow);border-top:5px solid var(--c)}
.tile b{display:block;font-size:40px;line-height:1.05;color:var(--c);font-variant-numeric:tabular-nums}
.tile span{font-size:13px;color:var(--muted);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow);min-width:0}
.need{position:relative}
.needcard{border-left:6px solid var(--you)}
.needcard .top{display:flex;gap:10px;align-items:flex-start}
.rank{flex:none;width:30px;height:30px;border-radius:50%;background:var(--you);color:var(--surface);font-weight:700;display:grid;place-items:center}
.score{margin-left:auto;flex:none;font-size:12px;font-weight:700;color:var(--you);background:var(--you-bg);border-radius:999px;padding:3px 9px;white-space:nowrap}
.needcard dl{margin:10px 0 0;display:grid;gap:6px}
.needcard dt{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700}
.needcard dd{margin:0}
.rec{background:var(--done-bg);border-radius:8px;padding:6px 9px}
.ex{background:var(--surface2);border-radius:8px;padding:6px 9px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
.where{margin-top:10px;font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;gap:4px;align-items:center;font-size:12px;background:var(--surface2);border:1px solid var(--line);border-radius:999px;padding:2px 9px;max-width:100%}
.chip b{color:var(--accent)}
.unb{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.unb>.k{font-weight:700;font-size:12px;color:var(--you)}
.ws{margin-bottom:14px}
.ws header{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.wsprog{font-size:12px;color:var(--muted)}
.chain{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;margin-top:6px;padding-bottom:4px}
.chain svg{display:block}
.hint{display:none;font-size:11px;color:var(--muted);text-align:right}
@media (max-width:1000px){.hint{display:block}}
.node rect{stroke-width:2}
.st-done rect{fill:var(--done-bg);stroke:var(--done)}
.st-active rect{fill:var(--active-bg);stroke:var(--active)}
.st-waiting rect{fill:var(--wait-bg);stroke:var(--wait);stroke-dasharray:6 3}
.st-blocked rect{fill:var(--block-bg);stroke:var(--block);stroke-width:3}
.st-todo rect{fill:var(--surface);stroke:var(--todo);stroke-dasharray:2 3}
.nt{fill:var(--ink);font-size:13px;font-weight:600}
.no{fill:var(--muted);font-size:11px}
.ext{fill:var(--accent);font-size:11px;font-weight:600}
.arr{fill:none;stroke:var(--muted);stroke-width:1.6}
.ahp{fill:var(--muted)}
.bdg{fill:var(--block)}.bdgt{fill:#fff;font-size:14px;font-weight:800}
.bdg-ok{fill:var(--done)}.tick{fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.cat{margin-top:22px}
.cat h3{color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-size:12px}
.sess{border-top:5px solid var(--sc);display:flex;flex-direction:column;gap:9px}
.sess header{display:flex;gap:10px;justify-content:space-between;align-items:flex-start}
.sh{min-width:0}
.sid{font-size:11px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.s-active{--sc:var(--active)}.s-you{--sc:var(--you)}.s-review{--sc:var(--review)}.s-waiting{--sc:var(--wait)}.s-done{--sc:var(--done)}.s-blocked{--sc:var(--block)}
.pills{display:flex;gap:6px;flex-wrap:wrap}
.pill{font-size:12px;font-weight:700;border-radius:999px;padding:2px 10px}
.p-active{background:var(--active-bg);color:var(--active)}.p-you{background:var(--you-bg);color:var(--you)}
.p-review{background:var(--review-bg);color:var(--review)}.p-waiting{background:var(--wait-bg);color:var(--wait)}
.p-done{background:var(--done-bg);color:var(--done)}.p-blocked{background:var(--block-bg);color:var(--block)}
.noreply{font-size:12px;font-weight:700;border-radius:999px;padding:1px 9px;border:1.5px dashed var(--block);color:var(--block)}
.plan{background:var(--surface2);border-radius:10px;padding:8px 10px}
.planpath{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:var(--muted)}
.barrow{display:flex;align-items:center;gap:8px;margin:5px 0}
.bar{flex:1;height:9px;border-radius:999px;background:var(--line);overflow:hidden}
.bar i{display:block;height:100%;background:var(--done);border-radius:999px}
.frac{font-size:12px;font-weight:700;font-variant-numeric:tabular-nums}
.chunk{font-size:13px}
.k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin-right:4px}
.row{display:grid;grid-template-columns:82px 1fr;gap:6px;font-size:14px}
.row.need{background:var(--you-bg);border-radius:8px;padding:5px 7px}
.row.need .k{color:var(--you)}
.prs{display:flex;flex-wrap:wrap;gap:6px}
.pr{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:700;border:1px solid var(--line);border-radius:7px;padding:2px 7px;background:var(--surface)}
.pr i{width:9px;height:9px;border-radius:50%;background:var(--todo)}
.pr small{font-weight:500;color:var(--muted)}
.ci-ok i{background:var(--done)}.ci-bad i{background:var(--block)}.ci-pend i{background:var(--wait)}
.ci-bad{border-color:var(--block)}
.gauge{flex:none;position:relative;width:46px;height:46px}
.gauge svg{width:46px;height:46px}
.gauge span{position:absolute;inset:0;display:grid;place-items:center;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums}
.gt{fill:none;stroke:var(--line);stroke-width:4}
.gv{fill:none;stroke-width:4;stroke-linecap:round}
.g-ok .gv{stroke:var(--done)}.g-amber .gv{stroke:var(--wait)}.g-red .gv{stroke:var(--block)}
.g-amber span{color:var(--wait)}.g-red span{color:var(--block)}
footer{font-size:12px;margin-top:auto}
ol.tl{list-style:none;margin:0;padding:0;position:relative}
ol.tl li{position:relative;padding:0 0 16px 48px}
ol.tl li:before{content:"";position:absolute;left:15px;top:30px;bottom:0;width:2px;background:var(--line)}
ol.tl li:last-child:before{display:none}
.tn{position:absolute;left:0;top:0;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;font-weight:800;background:var(--active-bg);color:var(--active);border:2px solid var(--active)}
.tn.nigel{background:var(--you-bg);color:var(--you);border-color:var(--you)}
.who{font-size:12px;font-weight:700;color:var(--muted)}
.tl .what{font-weight:600}
.tl .after{margin-top:4px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12px}
ul.recent{list-style:none;margin:0;padding:0}
ul.recent li{display:grid;grid-template-columns:120px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}
ul.recent li:last-child{border-bottom:0}
ul.recent time{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.legend{display:flex;flex-wrap:wrap;gap:14px 22px;font-size:13px}
.legend span{display:inline-flex;align-items:center;gap:7px}
.sw{width:22px;height:14px;border-radius:4px;border:2px solid}
.sw.done{background:var(--done-bg);border-color:var(--done)}
.sw.active{background:var(--active-bg);border-color:var(--active)}
.sw.waiting{background:var(--wait-bg);border-color:var(--wait);border-style:dashed}
.sw.blocked{background:var(--block-bg);border-color:var(--block);border-width:3px}
.sw.todo{background:var(--surface);border-color:var(--todo);border-style:dotted}
.dot{width:10px;height:10px;border-radius:50%}
.empty{padding:14px 16px;border:1px dashed var(--line);border-radius:12px;color:var(--muted)}
/* sessions as full-width rows */
.rows{display:flex;flex-direction:column;gap:14px}
.sess{gap:12px;padding:16px 18px}
.sess .pills{margin-top:6px;align-items:center}
.upd{font-size:12px}
.sgrid{display:grid;grid-template-columns:1fr;gap:12px 22px}
@media (min-width:760px){.sgrid{grid-template-columns:1fr 1fr}}
@media (min-width:1100px){.sgrid{grid-template-columns:1.2fr 1fr 1fr}}
.scol{display:flex;flex-direction:column;gap:10px;min-width:0}
.fld{font-size:14px;min-width:0}
.fld>.k{display:block;margin-bottom:3px}
.fld.need{background:var(--you-bg);border-radius:8px;padding:7px 9px}
.fld.need>.k{color:var(--you)}
.expls{display:flex;flex-direction:column;gap:12px}
.expl{display:inline-flex;gap:6px;align-items:baseline;font-weight:600;font-size:14px;color:var(--active)}
.expl small{color:var(--muted);font-weight:500}
.explf{margin:0}
.explf iframe{display:block;width:100%;height:var(--h,360px);border:1px solid var(--line);border-radius:10px;background:#fff}
.explf figcaption{font-size:13px;color:var(--muted);margin-top:6px}
.explf a,.expl{color:var(--active)}
/* decisions */
.decwrap{border:2px solid var(--you);border-radius:18px;padding:18px;background:var(--you-bg)}
.decwrap>h2{margin-top:0}
.dechead{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;margin:-4px 0 14px}
.qcount{font-weight:800;font-size:15px;color:var(--you)}
.qmeter{flex:1;min-width:120px;max-width:320px;height:10px;border-radius:999px;background:var(--surface);border:1px solid var(--line);overflow:hidden}
.qmeter i{display:block;height:100%;width:0;background:var(--done);transition:width .3s}
.dbmsg{font-size:14px;border-radius:10px;padding:9px 12px;background:var(--surface);border:1px solid var(--line)}
.dbmsg.bad{border-color:var(--block);color:var(--block);background:var(--block-bg)}
.qlist{display:flex;flex-direction:column;gap:16px}
.qcard{padding:20px 22px;border-left:6px solid var(--you)}
.qcard.is-answered{border-left-color:var(--done)}
.qh{display:flex;gap:12px;align-items:flex-start}
.qh h3{font-size:18px;margin:2px 0 0;flex:1}
.qid{flex:none;font-weight:800;font-size:13px;color:var(--you);background:var(--you-bg);border-radius:8px;padding:4px 9px}
.qbadge{flex:none;font-size:12px;font-weight:700;color:var(--done);background:var(--done-bg);border-radius:999px;padding:3px 10px}
.ctx{margin:12px 0;font-size:15px;max-width:880px}
.exbox{background:var(--active-bg);border-left:4px solid var(--active);border-radius:10px;padding:10px 14px;margin:0 0 14px;max-width:880px}
.exbox .k{color:var(--active)}
.exbox p{margin:3px 0 0}
fieldset{border:0;margin:0;padding:0;min-width:0}
legend{padding:0;margin-bottom:8px}
.opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:10px}
.opt{position:relative;display:flex;gap:12px;align-items:flex-start;cursor:pointer;background:var(--surface);border:2px solid var(--line);border-radius:12px;padding:14px 16px;min-height:72px}
.opt:hover{border-color:var(--muted)}
.opt input{flex:none;width:20px;height:20px;margin:2px 0 0;accent-color:var(--you)}
.opt:has(input:checked){border-color:var(--you);background:var(--you-bg);box-shadow:0 0 0 2px var(--you) inset}
.opt:has(input:focus-visible){outline:3px solid var(--active);outline-offset:2px}
.opt.is-rec{border-style:solid}
.ob{display:flex;flex-direction:column;gap:3px;min-width:0}
.ol{font-weight:700;font-size:15px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.okey{font-size:12px;color:var(--muted);text-transform:uppercase}
.od{font-size:13px;color:var(--muted)}
.badge{font-size:11px;font-weight:800;color:var(--done);background:var(--done-bg);border:1px solid var(--done);border-radius:999px;padding:1px 8px;text-transform:uppercase;letter-spacing:.04em}
.why{margin-top:12px;background:var(--done-bg);border-radius:10px;padding:10px 14px;max-width:880px}
.why .k{color:var(--done)}
.why p{margin:3px 0 0}
.note{display:block;margin-top:14px;max-width:880px}
.note .k{display:block;margin-bottom:4px}
textarea{width:100%;font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:9px 11px;resize:vertical}
.qact{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:14px}
.btn{font:inherit;font-weight:700;font-size:14px;border-radius:10px;padding:9px 18px;border:2px solid var(--you);cursor:pointer;background:var(--surface);color:var(--you)}
.btn.primary{background:var(--you);color:var(--surface)}
.btn.ghost{border-color:var(--line);color:var(--ink)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.savemsg{font-size:13px;color:var(--muted)}
.savemsg.bad{color:var(--block)}
.answered{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin-top:12px;background:var(--done-bg);border-radius:10px;padding:10px 14px}
.answered .k{color:var(--done)}
.answered .alabel{font-size:15px}
.answered .change{margin-left:auto}
.decided{margin-top:16px;padding:12px 16px}
.decided summary{cursor:pointer;font-weight:700}
.decided ul{list-style:none;margin:10px 0 0;padding:0}
.decided li{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:baseline;padding:6px 0;border-top:1px solid var(--line);font-size:14px}
.decided time{font-size:12px;color:var(--muted)}
.n{font-size:12px;font-weight:600;color:var(--muted);background:var(--surface2);border:1px solid var(--line);border-radius:999px;padding:1px 8px}
.doneact{margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.doneact .btn{padding:6px 14px;font-size:13px}
.btn[aria-pressed="true"]{background:var(--done);border-color:var(--done);color:var(--surface)}
.needcard.is-done{border-left-color:var(--done);opacity:.8}
.needcard.is-done h3{text-decoration:line-through;text-decoration-thickness:1px}
@media (max-width:520px){.explf iframe{height:calc(var(--h,360px) * 1.6)}}
@media (max-width:520px){.decwrap{padding:12px;border-radius:14px}.qcard{padding:14px}.decided li{grid-template-columns:auto 1fr}.decided time{grid-column:2}.answered .change{margin-left:0}}
@media (max-width:520px){
  h1{font-size:22px}.tile b{font-size:32px}.row{grid-template-columns:1fr;gap:0}
  ul.recent li{grid-template-columns:1fr;gap:2px}
}
"""


JS = r"""
(function () {
  "use strict";
  function readJSON(id) {
    try { var el = document.getElementById(id); return el ? JSON.parse(el.textContent || "[]") : []; }
    catch (err) { return []; }
  }
  var QS = readJSON("q-data"), ACTS = readJSON("a-data");
  var byId = {};
  QS.forEach(function (q) { byId[q.id] = q; });
  var SAFE = /^[A-Za-z0-9_\-.~:@+]{1,200}$/;
  var answers = {}, db = null, uid = null, writable = true;
  var msg = document.getElementById("db-msg");
  var countEl = document.getElementById("q-count"), meter = document.getElementById("q-meter");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".qcard[data-qid]"));

  function say(text, bad) {
    if (!msg) return;
    msg.textContent = text;
    msg.className = "dbmsg" + (bad ? " bad" : "");
    msg.hidden = !text;
  }
  function counter() {
    var n = 0;
    QS.forEach(function (q) { if (answers[q.id]) n++; });
    if (countEl) countEl.textContent = n + " of " + QS.length + " answered";
    if (meter) meter.style.width = (QS.length ? (100 * n / QS.length) : 0) + "%";
  }
  function retryOnce(fn) {
    return fn().catch(function (err) {
      if (err && err.code === "unavailable") {
        return new Promise(function (r) { setTimeout(r, 400 + Math.random() * 600); }).then(fn);
      }
      throw err;
    });
  }
  function errText(err) {
    var c = err && err.code;
    if (c === "invalid_argument") return "You can read this page but not save on it (your access is view-only).";
    if (c === "quota_exceeded") return "The answer store is full; tell the coordinator.";
    if (c === "resource_exhausted") return "Too many saves at once; wait a moment and try again.";
    if (c === "revoked" || c === "not_granted" || c === "capability_disabled" || c === "capability_removed")
      return "Saving is not available in this view.";
    return "Could not save (" + (c || "unknown error") + "). Try again.";
  }

  function chosen(card) {
    var r = card.querySelector('input[type="radio"]:checked');
    return r ? r.value : null;
  }
  function paint(card) {
    var qid = card.getAttribute("data-qid"), a = answers[qid];
    var ans = card.querySelector(".answered"), body = card.querySelector(".qbody");
    var badge = card.querySelector(".qbadge"), cancel = card.querySelector(".cancel");
    var editing = card.getAttribute("data-editing") === "1";
    if (a && !editing) {
      card.classList.add("is-answered");
      ans.hidden = false; body.hidden = true;
      ans.querySelector(".alabel").textContent = (a.choice ? a.choice + ". " : "") + (a.option_label || "");
      ans.querySelector(".anote").textContent = a.note ? "Note: " + a.note : "";
      badge.hidden = false; badge.textContent = "Answered";
    } else {
      card.classList.toggle("is-answered", !!a);
      ans.hidden = true; body.hidden = false;
      badge.hidden = !a; badge.textContent = a ? "Answered" : "";
      cancel.hidden = !(a && editing);
    }
    var save = card.querySelector(".save");
    save.disabled = !(db && writable && chosen(card));
  }
  function fill(card) {
    var a = answers[card.getAttribute("data-qid")];
    if (!a) return;
    card.querySelectorAll('input[type="radio"]').forEach(function (r) { r.checked = r.value === a.choice; });
    card.querySelector("textarea").value = a.note || "";
  }

  cards.forEach(function (card) {
    var qid = card.getAttribute("data-qid");
    var out = card.querySelector(".savemsg");
    card.querySelectorAll('input[type="radio"]').forEach(function (r) {
      r.addEventListener("change", function () { paint(card); });
    });
    card.querySelector(".change").addEventListener("click", function () {
      card.setAttribute("data-editing", "1"); fill(card); paint(card);
      var first = card.querySelector('input[type="radio"]:checked') || card.querySelector('input[type="radio"]');
      if (first) first.focus();
    });
    card.querySelector(".cancel").addEventListener("click", function () {
      card.removeAttribute("data-editing"); out.textContent = ""; paint(card);
    });
    card.querySelector("form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var key = chosen(card);
      if (!db || !key || !SAFE.test(qid)) return;
      var q = byId[qid] || { title: "", options: [] };
      var opt = (q.options || []).filter(function (o) { return o.key === key; })[0];
      var note = card.querySelector("textarea").value.trim().slice(0, 4000);
      var body = { choice: key, option_label: opt ? opt.label : key, note: note,
                   at: new Date().toISOString(), title: q.title || "" };
      if (uid) body.by = uid;
      var save = card.querySelector(".save");
      save.disabled = true; out.className = "savemsg"; out.textContent = "Saving…";
      retryOnce(function () { return db.collection("answers").doc(qid).set(body); }).then(function () {
        answers[qid] = body; card.removeAttribute("data-editing");
        out.textContent = "Saved."; counter(); paint(card);
      }, function (err) {
        if (err && err.code === "invalid_argument") writable = false;
        out.className = "savemsg bad"; out.textContent = errText(err); paint(card);
      });
    });
    paint(card);
  });

  var doneState = {};
  var toggles = Array.prototype.slice.call(document.querySelectorAll(".done-toggle[data-aid]"));
  function paintToggle(btn) {
    var id = btn.getAttribute("data-aid"), d = doneState[id];
    var on = !!(d && d.done);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.textContent = on ? "Done ✓ (undo)" : "I've done this";
    btn.disabled = !(db && writable);
    var card = btn.closest(".needcard");
    if (card) card.classList.toggle("is-done", on);
  }
  toggles.forEach(function (btn) {
    var id = btn.getAttribute("data-aid");
    var out = btn.parentNode.querySelector(".savemsg");
    btn.addEventListener("click", function () {
      if (!db || !SAFE.test(id)) return;
      var a = ACTS.filter(function (x) { return x.id === id; })[0];
      var next = !(doneState[id] && doneState[id].done);
      var body = { done: next, at: new Date().toISOString(), title: a ? a.title : "" };
      if (uid) body.by = uid;
      btn.disabled = true; out.className = "savemsg"; out.textContent = "Saving…";
      retryOnce(function () { return db.collection("actions").doc(id).set(body); }).then(function () {
        doneState[id] = body; out.textContent = next ? "Recorded." : "Undone."; paintToggle(btn);
      }, function (err) {
        if (err && err.code === "invalid_argument") writable = false;
        out.className = "savemsg bad"; out.textContent = errText(err); paintToggle(btn);
      });
    });
  });

  function offline(text) {
    db = null;
    say(text, true);
    if (countEl) countEl.textContent = "Answers can't be loaded in this view";
    cards.forEach(paint); toggles.forEach(paintToggle);
  }

  var claude = window.claude;
  if (!claude || typeof claude.use !== "function") {
    offline("Saving is unavailable here (this copy of the page is not opened in Claude). Everything stays readable; answer in the coordinator session instead.");
    return;
  }
  Promise.resolve().then(function () { return claude.use("db"); }).then(function (handle) {
    if (!handle) {
      offline("The answer store is unavailable in this view (signed out, or not granted). Everything stays readable; answer in the coordinator session instead.");
      return null;
    }
    db = handle;
    return Promise.resolve().then(function () { return claude.use("user"); })
      .then(function (u) { return u ? u.id() : null; }, function () { return null; })
      .then(function (id) { uid = id || null; })
      .then(function () {
        return Promise.all([
          retryOnce(function () { return db.collection("answers").get(); }),
          retryOnce(function () { return db.collection("actions").get(); })
        ]);
      })
      .then(function (snaps) {
        snaps[0].docs.forEach(function (d) {
          var v = d.exists ? d.data() : null;
          if (v && typeof v === "object" && byId[d.id] && typeof v.choice === "string") answers[d.id] = v;
        });
        snaps[1].docs.forEach(function (d) {
          var v = d.exists ? d.data() : null;
          if (v && typeof v === "object") doneState[d.id] = v;
        });
        say("", false); counter(); cards.forEach(paint); toggles.forEach(paintToggle);
      });
  }).catch(function (err) {
    offline("Answers could not be loaded (" + ((err && err.code) || "error") + "). Everything stays readable; reload to try again.");
  });
})();
"""

EMPTY_Q = '<div class="empty">No open questions.</div>'


def render(data: dict) -> str:
    labels = label_index(data)
    graph = dependents(data)
    sessions = [s for s in as_list(data.get("sessions")) if isinstance(s, dict)]
    needs = [n for n in as_list(data.get("needs_nigel")) if isinstance(n, dict)]

    def count(*states: str) -> int:
        return sum(1 for s in sessions if s.get("state") in states)

    tiles = [
        ("Working", count("working"), "--active"),
        ("Waiting on you", count("waiting-on-nigel"), "--you"),
        ("Blocked", count("blocked"), "--block"),
        ("Done", count("done"), "--done"),
        ("Other waits", count("waiting-on-review", "waiting-on-other-session"), "--review"),
        ("Asks for you", len(needs), "--accent"),
    ]
    tiles_html = "".join(
        f'<div class="tile" style="--c:var({c})"><b>{n}</b><span>{e(t)}</span></div>'
        for t, n, c in tiles
    )

    # Needs you, ranked by how much each unblocks (transitively)
    ranked = []
    for idx, n in enumerate(needs):
        reached = reach(as_list(n.get("unblocks")), graph) - {str(n.get("id"))}
        ranked.append((-len(reached), idx, n, len(reached)))
    ranked.sort(key=lambda t: (t[0], t[1]))
    need_cards = []
    for rank, (_, _, n, score) in enumerate(ranked, 1):
        unb = "".join(chip(str(u), labels) for u in as_list(n.get("unblocks")))
        dl = []
        if n.get("why"):
            dl.append(f"<dt>Why</dt><dd>{e(n.get('why'))}</dd>")
        if n.get("example"):
            dl.append(f'<dt>Example</dt><dd class="ex">{e(n.get("example"))}</dd>')
        if n.get("recommendation"):
            dl.append(f'<dt>Recommendation</dt><dd class="rec">{e(n.get("recommendation"))}</dd>')
        need_cards.append(
            f'<article class="card needcard" data-aid="{e(n.get("id"))}"><div class="top"><span class="rank">{rank}</span>'
            f'<h3><span class="muted">{e(n.get("id"))}</span> {e(n.get("title"))}</h3>'
            f'<span class="score" title="Steps that wait on this, directly or indirectly">unblocks {score}</span></div>'
            f"<dl>{''.join(dl)}</dl>"
            + (f'<div class="unb"><span class="k">unblocks →</span>{unb}</div>' if unb else "")
            + (
                f'<div class="where"><span class="k">Where</span>{e(n.get("where"))}</div>'
                if n.get("where")
                else ""
            )
            + f'<div class="doneact"><button type="button" class="btn done-toggle" data-aid="{e(n.get("id"))}" '
            f'aria-pressed="false" disabled>I\'ve done this</button><span class="savemsg" role="status" aria-live="polite"></span></div>'
            + "</article>"
        )
    needs_html = (
        f'<div class="grid">{"".join(need_cards)}</div>'
        if need_cards
        else '<div class="empty">Nothing waits on you.</div>'
    )

    questions = [q for q in as_list(data.get("questions")) if isinstance(q, dict) and q.get("id")]
    q_cards = "".join(question_card(q, labels) for q in questions)
    q_data = [
        {
            "id": str(q.get("id")),
            "title": str(q.get("title") or ""),
            "options": [
                {"key": str(o.get("key") or ""), "label": str(o.get("label") or "")}
                for o in as_list(q.get("options"))
                if isinstance(o, dict)
            ],
        }
        for q in questions
    ]
    a_data = [
        {"id": str(n.get("id")), "title": str(n.get("title") or "")} for n in needs if n.get("id")
    ]
    decided = decided_html(as_list(data.get("decided")))
    decisions_html = (
        f'<section class="decwrap" id="decisions" aria-labelledby="dec-h"><h2 id="dec-h">Your decisions '
        f'<span class="n">{len(questions)}</span></h2>'
        f'<div class="dechead"><span class="qcount" id="q-count">Loading answers… (of {len(questions)})</span>'
        f'<span class="qmeter" aria-hidden="true"><i id="q-meter"></i></span></div>'
        f'<div class="dbmsg" id="db-msg" role="status">Connecting to the answer store… The questions are readable now; '
        f"Save switches on once the store answers.</div>"
        f'<div class="qlist" style="margin-top:14px">{q_cards or EMPTY_Q}</div>'
        f"{decided}</section>"
    )

    # Workstreams
    ws_html = []
    for w in as_list(data.get("workstreams")):
        if not isinstance(w, dict):
            continue
        steps = [s for s in as_list(w.get("steps")) if isinstance(s, dict)]
        done = sum(1 for s in steps if s.get("status") == "done")
        blocked = sum(1 for s in steps if s.get("status") == "blocked")
        extra = f' · <b style="color:var(--block)">{blocked} blocked</b>' if blocked else ""
        ws_html.append(
            f'<section class="card ws"><header><h3>{e(w.get("title"))}</h3>'
            f'<span class="wsprog">{done}/{len(steps)} done{extra}</span></header>{chain_svg(w, labels)}</section>'
        )

    # Sessions by category
    groups: dict[str, list[dict]] = {}
    for s in sessions:
        cat = str(s.get("category") or s.get("role") or "Other")
        groups.setdefault(cat, []).append(s)
    order = [c for c in CATEGORY_ORDER if c in groups] + sorted(
        c for c in groups if c not in CATEGORY_ORDER
    )
    sess_html = []
    for cat in order:
        cards = "".join(session_card(s, labels) for s in groups[cat])
        sess_html.append(
            f'<div class="cat"><h3>{e(cat)} · {len(groups[cat])}</h3><div class="rows">{cards}</div></div>'
        )
    noreply = [s for s in sessions if s.get("reply") == "no reply"]

    # Next
    tl = []
    for i, a in enumerate(as_list(data.get("next_actions")), 1):
        if not isinstance(a, dict):
            continue
        who = str(a.get("who") or "")
        after = "".join(chip(str(x), labels) for x in as_list(a.get("after")))
        tl.append(
            f'<li><span class="tn{" nigel" if "nigel" in who.lower() else ""}">{i}</span>'
            f'<div class="who">{e(who)} <span class="muted">· {e(a.get("id"))}</span></div>'
            f'<div class="what">{e(a.get("what"))}</div>'
            + (f'<div class="after"><span class="k">after</span>{after}</div>' if after else "")
            + "</li>"
        )

    recent = sorted(
        (r for r in as_list(data.get("recent")) if isinstance(r, dict)),
        key=lambda r: str(r.get("when") or ""),
        reverse=True,
    )
    recent_html = "".join(
        f"<li><time>{e(short_time(r.get('when')))}</time><span>{e(r.get('what'))}</span></li>"
        for r in recent
    )

    legend = (
        '<div class="legend">'
        + "".join(f'<span><i class="sw {k}"></i>{v}</span>' for k, v in STEP_STATUS.items())
        + '<span><i class="dot" style="background:var(--done)"></i>CI green</span>'
        '<span><i class="dot" style="background:var(--wait)"></i>CI pending</span>'
        '<span><i class="dot" style="background:var(--block)"></i>CI red</span>'
        '<span><i class="dot" style="background:var(--todo)"></i>no CI</span>'
        "<span>Context gauge: green &lt; 60 %, amber 60-69 %, red ≥ 70 % (handoff due)</span>"
        "<span>↳ after x: waits on a step in another workstream</span>"
        "</div>"
    )

    gen = short_time(data.get("generated_at")) or "unknown time"
    sha = e(data.get("develop_sha")) or "unknown"
    nr = f' · <b style="color:var(--block)">{len(noreply)} no reply</b>' if noreply else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIA PM Status</title><style>{CSS}</style></head>
<body><main>
<h1>AIA PM Status</h1>
<div class="meta">Generated {e(gen)} · develop @ <code>{sha}</code> · {len(sessions)} sessions{nr}</div>
<p class="headline">{e(data.get("headline"))}</p>
<div class="tiles">{tiles_html}</div>

<div style="margin-top:28px">{decisions_html}</div>

<h2>Actions only you can take <span class="n">{len(needs)}</span></h2>
<p class="muted" style="margin-top:-6px">Ranked by how many steps each unblocks. Press "I've done this" when you have.</p>
{needs_html}

<h2>Workstreams and dependencies</h2>
{"".join(ws_html) or '<div class="empty">No workstreams.</div>'}

<h2>Sessions <span class="n">{len(sessions)}</span></h2>
{"".join(sess_html) or '<div class="empty">No sessions.</div>'}

<h2>What's next</h2>
<div class="card">{f'<ol class="tl">{"".join(tl)}</ol>' if tl else '<span class="muted">Nothing queued.</span>'}</div>

<h2>Done in the last 24 h</h2>
<div class="card">{f'<ul class="recent">{recent_html}</ul>' if recent_html else '<span class="muted">Nothing recorded.</span>'}</div>

<h2>Legend</h2>
<div class="card">{legend}</div>
</main>
{json_script("q-data", q_data)}
{json_script("a-data", a_data)}
<script>{JS}</script>
</body></html>
"""


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: render.py status.json out.html", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        print("status.json must be an object", file=sys.stderr)
        return 1
    with open(argv[2], "w", encoding="utf-8") as fh:
        fh.write(render(data))
    print(f"wrote {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
