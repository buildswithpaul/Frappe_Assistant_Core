# Frappe Assistant Core - Rich block rendering for PDF generation
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Pre-process rich code fences in LLM markdown before PDF rendering.

The chat surface already understands fences like ``` ```chart ```, ``` ```callout ```,
and ``` ```metric ``` (see frontend ``richBlocks/parser.js``). For PDFs we want
the same dialect to work — the agent writes one markdown document, the user
sees the same visuals on screen and in the downloaded file.

This module substitutes those fences with self-contained HTML (inline SVG
for charts, styled divs for callouts/metrics) **before** the markdown
goes through ``md_to_html`` and bleach. The substituted HTML uses an
``<x-rich>`` wrapper carrying a token; we restore the real HTML after
bleach has sanitised the rest, so chart SVGs and styled blocks survive
intact while LLM-authored HTML is still scrubbed.
"""

from __future__ import annotations

import html
import json
import math
import re
import uuid
from typing import Any

# ``` blocks with our recognised types. Attributes are optional; body
# may be empty for self-attribute components like ``metric``.
_FENCE_RE = re.compile(
    r"```(chart|callout|metric|cover|pagebreak)([ \t]+[^\n]*)?\n([\s\S]*?)```",
    re.MULTILINE,
)

_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

# Palette mirrors the frontend ChartRenderer default series colors so the
# PDF and chat look visually consistent. Order matters — series 0 → 0, etc.
_CHART_PALETTE = (
    "#5470c6",
    "#91cc75",
    "#fac858",
    "#ee6666",
    "#73c0de",
    "#3ba272",
    "#fc8452",
    "#9a60b4",
)

_CALLOUT_STYLES = {
    "info": {"bg": "#eff6ff", "border": "#3b82f6", "icon": "i"},
    "tip": {"bg": "#ecfdf5", "border": "#10b981", "icon": "★"},
    "success": {"bg": "#ecfdf5", "border": "#10b981", "icon": "✓"},
    "warning": {"bg": "#fffbeb", "border": "#f59e0b", "icon": "!"},
    "error": {"bg": "#fef2f2", "border": "#ef4444", "icon": "✕"},
}


def preprocess_rich_blocks(markdown: str) -> tuple[str, dict[str, str]]:
    """Replace rich fences with placeholder tokens and return the substitutions.

    Returns ``(markdown_with_tokens, token_to_html)``. Callers should run
    the rest of the markdown→HTML→sanitise pipeline on the first value,
    then call :func:`restore_rich_blocks` with the second.
    """
    tokens: dict[str, str] = {}

    def _substitute(match: re.Match[str]) -> str:
        block_type = match.group(1)
        attr_string = (match.group(2) or "").strip()
        body = (match.group(3) or "").strip()
        attrs = _parse_attrs(attr_string)

        try:
            rendered = _render_block(block_type, attrs, body)
        except Exception:
            # Fall back to a plain code block on any parse/render error so
            # the document still produces — we never want a malformed
            # chart fence to fail the whole PDF.
            rendered = f"<pre><code>{html.escape(body)}</code></pre>"

        # Token must survive both md_to_html and bleach. md_to_html
        # interprets ``_`` and ``__`` as emphasis, so we can't use a
        # uuid-shaped placeholder directly in the text. Instead we emit a
        # raw HTML span — md_to_html passes inline HTML through verbatim,
        # and bleach already permits ``span class=...`` (see _ALLOWED_TAGS
        # in generate_document.py). The class itself carries the uuid;
        # the restore pass matches the full element by class.
        marker = uuid.uuid4().hex
        token_html = f'<span class="faco-rich-{marker}"></span>'
        tokens[marker] = rendered
        # Blank lines around so the span sits in its own block.
        return f"\n\n{token_html}\n\n"

    processed = _FENCE_RE.sub(_substitute, markdown)
    return processed, tokens


def restore_rich_blocks(html_body: str, tokens: dict[str, str]) -> str:
    """Restore rich-block HTML after sanitisation.

    After ``md_to_html`` and bleach, each placeholder span survives as
    ``<p><span class="faco-rich-<marker>"></span></p>`` (the surrounding
    ``<p>`` is added by the markdown parser around inline HTML on its
    own line). We replace the whole wrapped span with the rendered
    rich-block HTML so charts/callouts/metrics sit flush in the
    document rather than nested inside an empty paragraph.
    """
    for marker, rendered in tokens.items():
        span_re = rf'<p>\s*<span\s+class="faco-rich-{marker}"\s*>\s*</span>\s*</p>'
        # First try the wrapped form (most common — markdown puts inline
        # HTML on its own line inside a <p>). Fall back to the bare span
        # (covers the case where the span ended up adjacent to other text).
        html_body, n = re.subn(span_re, rendered, html_body, count=1)
        if n == 0:
            bare_re = rf'<span\s+class="faco-rich-{marker}"\s*>\s*</span>'
            html_body = re.sub(bare_re, rendered, html_body, count=1)
    return html_body


def _parse_attrs(attr_string: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _ATTR_RE.finditer(attr_string)}


def _render_block(block_type: str, attrs: dict[str, str], body: str) -> str:
    if block_type == "chart":
        spec = json.loads(body) if body else {}
        return _render_chart(spec)
    if block_type == "callout":
        return _render_callout(attrs, body)
    if block_type == "metric":
        return _render_metric(attrs, body)
    if block_type == "cover":
        return _render_cover(attrs, body)
    if block_type == "pagebreak":
        return '<div class="page-break"></div>'
    # Unknown — emit a plain pre.
    return f"<pre><code>{html.escape(body)}</code></pre>"


# ---------------------------------------------------------------------------
# Callout / metric / cover — styled HTML
# ---------------------------------------------------------------------------


def _render_callout(attrs: dict[str, str], body: str) -> str:
    """Render a callout from fence attributes or a JSON body.

    Attributes are the documented dialect, but the model generalises from the
    ``chart`` fence beside it and will write
    ``{"type":…,"title":…,"content":…}`` instead — which rendered an *info*
    box with no title and the raw JSON as its text. Both dialects are
    accepted here and in the chat-side renderers so one reply looks the same
    on screen and in the download. Attributes win when a fence carries both,
    and an unrecognised JSON shape keeps its body visible rather than
    collapsing to an empty box.
    """
    pick = _body_picker(attrs, _json_object_body(body))
    style = _CALLOUT_STYLES.get(pick("type") or "info", _CALLOUT_STYLES["info"])
    title = pick("title", "heading")
    # Body may contain inline markdown; we keep it simple — bold and code
    # only, since callout bodies are short by convention.
    body_html = _inline_markdown(pick("content", "body", "text", "message") or body)
    title_html = f'<div class="callout-title">{html.escape(title)}</div>' if title else ""
    return (
        f'<div class="callout" style="background:{style["bg"]};border-left-color:{style["border"]}">'
        f'<div class="callout-icon" style="color:{style["border"]}">{style["icon"]}</div>'
        f'<div class="callout-body">{title_html}{body_html}</div>'
        f"</div>"
    )


def _parse_json_body(body: str) -> dict[str, Any] | list[Any] | None:
    """A fence body parsed as JSON, or ``None`` when it isn't JSON.

    The model reaches for a JSON body on any fence, having generalised from
    the ``chart``/``mermaid`` fences documented beside them. Every block that
    documents fence-line attributes has to read one too, or the payload the
    model meant as structure reaches the reader as punctuation.
    """
    trimmed = (body or "").strip()
    if not trimmed.startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(trimmed)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _json_object_body(body: str) -> dict[str, Any]:
    """A JSON body as a plain dict; ``{}`` for an array or non-JSON body."""
    parsed = _parse_json_body(body)
    return parsed if isinstance(parsed, dict) else {}


def _body_picker(attrs: dict[str, str], json_body: dict[str, Any]):
    """First non-empty value for the given keys, attributes before JSON body.

    Attributes win because they are the documented dialect — a fence carrying
    both is a model hedging, and the explicit form is the stated intent.
    """

    def pick(*keys: str) -> str:
        for key in keys:
            if attrs.get(key):
                return str(attrs[key])
        for key in keys:
            value = json_body.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    return pick


def _render_metric(attrs: dict[str, str], body: str = "") -> str:
    """Render one KPI card, or a row of them.

    Data arrives three ways: fence attributes (the documented dialect), a
    JSON object keyed on ``label``/``value`` (what the model writes most of
    the time, having generalised from the ``chart`` fence next to it), or a
    JSON *array* — a whole KPI row in one fence. All three are accepted here
    and in the chat-side renderers so one reply renders identically on screen
    and in the download. Attributes win when a fence carries both.
    """
    parsed = _parse_json_body(body)

    if isinstance(parsed, list):
        cards = [_metric_card(attrs, entry if isinstance(entry, dict) else {}, body) for entry in parsed]
        rendered = [card for card in cards if card]
        if rendered:
            return "".join(rendered)
        return f"<pre><code>{html.escape(body)}</code></pre>"

    return _metric_card(attrs, parsed or {}, body) or (f"<pre><code>{html.escape(body)}</code></pre>")


def _metric_card(attrs: dict[str, str], json_body: dict[str, Any], body: str) -> str:
    """One KPI card, or ``""`` when neither a title nor a value is given."""
    pick = _body_picker(attrs, json_body)

    title = pick("title", "label")
    value = pick("value")
    change = pick("change", "delta")
    trend = pick("trend") or "flat"
    description = pick("description", "suffix")

    # Nothing renderable. The caller keeps the raw fence visible instead: an
    # empty card reads as a rendering glitch and gives the reader no clue the
    # fence was malformed.
    if not title and not value:
        return ""

    trend_color = {"up": "#10b981", "down": "#ef4444", "flat": "#6b7280"}.get(trend, "#6b7280")
    trend_arrow = {"up": "▲", "down": "▼", "flat": "▬"}.get(trend, "")
    change_html = (
        f'<span class="metric-change" style="color:{trend_color}">{trend_arrow} {html.escape(change)}</span>'
        if change
        else ""
    )
    description_html = (
        f'<div class="metric-description">{html.escape(description)}</div>' if description else ""
    )
    return (
        f'<div class="metric-card">'
        f'<div class="metric-title">{html.escape(title)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f"{change_html}"
        f"{description_html}"
        f"</div>"
    )


def _render_cover(attrs: dict[str, str], body: str) -> str:
    title = html.escape(attrs.get("title", ""))
    subtitle = html.escape(attrs.get("subtitle", ""))
    author = html.escape(attrs.get("author", ""))
    date = html.escape(attrs.get("date", ""))
    body_html = _inline_markdown(body) if body else ""
    # Build conditional fragments outside the f-string. Nesting a quoted
    # f-string inside the outer one (with escaped quotes) only parses on
    # Python 3.12+ (PEP 701) and raised a SyntaxError on 3.11, which silently
    # dropped this whole module — and the generate_document tool with it.
    subtitle_html = f'<p class="cover-subtitle">{subtitle}</p>' if subtitle else ""
    author_html = f"<div>{author}</div>" if author else ""
    date_html = f"<div>{date}</div>" if date else ""
    return (
        f'<section class="cover-page">'
        f'<div class="cover-inner">'
        f'<h1 class="cover-title">{title}</h1>'
        f"{subtitle_html}"
        f"{body_html}"
        f'<div class="cover-meta">'
        f"{author_html}"
        f"{date_html}"
        f"</div>"
        f"</div>"
        f"</section>"
    )


def _inline_markdown(text: str) -> str:
    """Very small inline-only markdown — bold, italic, code, line breaks.

    We don't want to recursively invoke the full markdown parser inside a
    callout body; the call is cheap to do manually and avoids the risk of
    a nested block fence breaking parsing.
    """
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+?)`", r"<code>\1</code>", escaped)
    escaped = escaped.replace("\n\n", "</p><p>")
    return f"<p>{escaped}</p>"


# ---------------------------------------------------------------------------
# Charts — pure-Python SVG
# ---------------------------------------------------------------------------
#
# Why not matplotlib? Adding a heavyweight dependency for four chart types
# that all reduce to a handful of SVG primitives isn't worth it.
# WeasyPrint and wkhtmltopdf both render inline SVG, so we emit SVG
# directly. The schema mirrors the frontend's ``categories``/``series``
# contract so the LLM only has to learn one dialect.


def _render_chart(spec: dict[str, Any]) -> str:
    chart_type = spec.get("type", "bar")
    title = spec.get("title", "")
    data = spec.get("data", {})
    categories = data.get("categories", [])
    series = data.get("series", [])

    if not categories or not series:
        return '<div class="chart-error">Missing or invalid chart data.</div>'

    renderers = {
        "bar": _svg_bar,
        "line": _svg_line,
        "pie": _svg_pie,
        "scatter": _svg_scatter,
    }
    renderer = renderers.get(chart_type, _svg_bar)
    svg = renderer(categories, series)
    title_html = f'<div class="chart-title">{html.escape(title)}</div>' if title else ""
    legend_html = _svg_legend(series) if len(series) > 1 or chart_type == "pie" else ""
    return f'<div class="chart-wrap">{title_html}{svg}{legend_html}</div>'


# SVG layout constants. Chosen to fit comfortably inside an A4 portrait
# content width (~180mm ≈ 680px at 96dpi) with breathing room.
_CHART_W = 640
_CHART_H = 320
_MARGIN_LEFT = 50
_MARGIN_RIGHT = 20
_MARGIN_TOP = 20
_MARGIN_BOTTOM = 50


def _plot_area() -> tuple[int, int, int, int]:
    x = _MARGIN_LEFT
    y = _MARGIN_TOP
    w = _CHART_W - _MARGIN_LEFT - _MARGIN_RIGHT
    h = _CHART_H - _MARGIN_TOP - _MARGIN_BOTTOM
    return x, y, w, h


def _svg_open() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_CHART_W} {_CHART_H}" '
        f'class="chart-svg" font-family="Helvetica, Arial, sans-serif" font-size="11">'
    )


def _nice_bounds(max_val: float, min_val: float = 0) -> tuple[float, float]:
    """Round (min, max) outward to nice round numbers for axis ticks.

    Returns ``(nice_min, nice_max)``. The bounds always include the raw
    data range and produce four evenly-spaced ticks between them.
    """
    if max_val == min_val:
        return min_val, max_val + 1
    span = max_val - min_val
    magnitude = 10 ** math.floor(math.log10(span))
    nice_max = math.ceil(max_val / magnitude) * magnitude
    # Floor min toward zero (or below, if data is negative) on the same
    # magnitude grid. Keeps the axis baseline clean.
    if min_val >= 0:
        nice_min = 0.0
    else:
        nice_min = math.floor(min_val / magnitude) * magnitude
    return nice_min, nice_max


def _fmt_tick(v: float) -> str:
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.1f}"


def _draw_axes(nice_max: float, nice_min: float = 0) -> str:
    """Draw y-axis gridlines and labels from pre-computed nice bounds.

    The caller must pass the *nice* bounds (use :func:`_nice_bounds`),
    not the raw data min/max — otherwise the topmost tick can land
    outside the plot area.
    """
    x, y, w, h = _plot_area()
    step = (nice_max - nice_min) / 4
    ticks = [nice_min + step * i for i in range(5)]
    pieces = []
    span = nice_max - nice_min or 1
    for tick in ticks:
        ratio = (tick - nice_min) / span
        ty = y + h - ratio * h
        pieces.append(
            f'<line x1="{x}" y1="{ty:.1f}" x2="{x + w}" y2="{ty:.1f}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        pieces.append(
            f'<text x="{x - 8}" y="{ty + 4:.1f}" text-anchor="end" fill="#6b7280">{_fmt_tick(tick)}</text>'
        )
    pieces.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + h}" stroke="#9ca3af" stroke-width="1"/>')
    pieces.append(
        f'<line x1="{x}" y1="{y + h}" x2="{x + w}" y2="{y + h}" stroke="#9ca3af" stroke-width="1"/>'
    )
    return "".join(pieces)


def _svg_bar(categories: list[Any], series: list[dict[str, Any]]) -> str:
    x, y, w, h = _plot_area()
    n_cats = len(categories)
    n_series = len(series)
    all_vals = [v for s in series for v in s.get("values", [])]
    if not all_vals:
        return _svg_open() + "</svg>"
    raw_max = max([*all_vals, 0])
    raw_min = min([*all_vals, 0])
    nice_min, nice_max = _nice_bounds(raw_max, raw_min)
    span = nice_max - nice_min or 1

    group_w = w / n_cats
    bar_pad = 8
    bar_w = max(2, (group_w - bar_pad) / n_series)

    bars = []
    for s_idx, s in enumerate(series):
        color = _CHART_PALETTE[s_idx % len(_CHART_PALETTE)]
        for c_idx, val in enumerate(s.get("values", [])):
            gx = x + c_idx * group_w + bar_pad / 2 + s_idx * bar_w
            ratio = (val - nice_min) / span
            bar_h = ratio * h
            by = y + h - bar_h
            bars.append(
                f'<rect x="{gx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'fill="{color}" rx="2"/>'
            )
    labels = []
    for c_idx, cat in enumerate(categories):
        lx = x + c_idx * group_w + group_w / 2
        labels.append(
            f'<text x="{lx:.1f}" y="{y + h + 18}" text-anchor="middle" fill="#374151">{html.escape(str(cat))}</text>'
        )

    return _svg_open() + _draw_axes(nice_max, nice_min) + "".join(bars) + "".join(labels) + "</svg>"


def _svg_line(categories: list[Any], series: list[dict[str, Any]]) -> str:
    x, y, w, h = _plot_area()
    n_cats = len(categories)
    all_vals = [v for s in series for v in s.get("values", [])]
    if not all_vals or n_cats < 2:
        return _svg_open() + "</svg>"
    raw_max = max(all_vals)
    raw_min = min(min(all_vals), 0)
    nice_min, nice_max = _nice_bounds(raw_max, raw_min)
    span = nice_max - nice_min or 1
    step_x = w / (n_cats - 1)

    lines = []
    for s_idx, s in enumerate(series):
        color = _CHART_PALETTE[s_idx % len(_CHART_PALETTE)]
        points = []
        for c_idx, val in enumerate(s.get("values", [])):
            px = x + c_idx * step_x
            ratio = (val - nice_min) / span
            py = y + h - ratio * h
            points.append((px, py))
        path = " ".join(f"{'M' if i == 0 else 'L'}{p[0]:.1f},{p[1]:.1f}" for i, p in enumerate(points))
        lines.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
        )
        for px, py in points:
            lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{color}"/>')

    labels = []
    for c_idx, cat in enumerate(categories):
        lx = x + c_idx * step_x
        labels.append(
            f'<text x="{lx:.1f}" y="{y + h + 18}" text-anchor="middle" fill="#374151">{html.escape(str(cat))}</text>'
        )

    return _svg_open() + _draw_axes(nice_max, nice_min) + "".join(lines) + "".join(labels) + "</svg>"


def _svg_pie(categories: list[Any], series: list[dict[str, Any]]) -> str:
    # Pie uses series[0] only — multi-series pies aren't a thing.
    if not series:
        return _svg_open() + "</svg>"
    values = series[0].get("values", [])
    total = sum(values) or 1
    cx, cy = _CHART_W / 2, _CHART_H / 2
    r = min(cx, cy) - 30

    slices = []
    angle = -math.pi / 2  # start at top
    for i, val in enumerate(values):
        frac = val / total
        end_angle = angle + frac * 2 * math.pi
        color = _CHART_PALETTE[i % len(_CHART_PALETTE)]
        large = 1 if frac > 0.5 else 0
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx + r * math.cos(end_angle)
        y2 = cy + r * math.sin(end_angle)
        slices.append(
            f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large} 1 {x2:.1f},{y2:.1f} Z" '
            f'fill="{color}" stroke="white" stroke-width="2"/>'
        )
        # Percentage label inside the slice for slices >= 5%.
        if frac >= 0.05:
            mid = (angle + end_angle) / 2
            lx = cx + r * 0.65 * math.cos(mid)
            ly = cy + r * 0.65 * math.sin(mid)
            slices.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="white" '
                f'font-weight="600">{frac * 100:.0f}%</text>'
            )
        angle = end_angle

    return _svg_open() + "".join(slices) + "</svg>"


def _svg_scatter(categories: list[Any], series: list[dict[str, Any]]) -> str:
    x, y, w, h = _plot_area()
    try:
        x_vals = [float(c) for c in categories]
    except (TypeError, ValueError):
        x_vals = list(range(len(categories)))
    all_y = [v for s in series for v in s.get("values", [])]
    if not all_y or not x_vals:
        return _svg_open() + "</svg>"
    x_min, x_max = min(x_vals), max(x_vals)
    y_nice_min, y_nice_max = _nice_bounds(max(all_y), min(min(all_y), 0))
    x_span = x_max - x_min or 1
    y_span = y_nice_max - y_nice_min or 1

    points = []
    for s_idx, s in enumerate(series):
        color = _CHART_PALETTE[s_idx % len(_CHART_PALETTE)]
        for c_idx, val in enumerate(s.get("values", [])):
            if c_idx >= len(x_vals):
                break
            px = x + ((x_vals[c_idx] - x_min) / x_span) * w
            py = y + h - ((val - y_nice_min) / y_span) * h
            points.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}" fill-opacity="0.75"/>')

    return _svg_open() + _draw_axes(y_nice_max, y_nice_min) + "".join(points) + "</svg>"


def _svg_legend(series: list[dict[str, Any]]) -> str:
    items = []
    for i, s in enumerate(series):
        color = _CHART_PALETTE[i % len(_CHART_PALETTE)]
        name = html.escape(str(s.get("name", f"Series {i + 1}")))
        items.append(
            f'<span class="legend-item"><span class="legend-swatch" '
            f'style="background:{color}"></span>{name}</span>'
        )
    return f'<div class="chart-legend">{"".join(items)}</div>'
