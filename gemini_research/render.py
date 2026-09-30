"""Render report.md into a single self-contained offline HTML page."""

import base64
import html
import json
import re
from functools import lru_cache
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors.index import slugify, unique_slug
from mdit_py_plugins.dollarmath import dollarmath_plugin

ASSETS = Path(__file__).parent / "assets"
KATEX = ASSETS / "katex"
DEF_RE = re.compile(r"^\[\^(\d+)\]: (.*)$")
REF_RE = re.compile(r"\[\^(\d+)\]")
FENCE_RE = re.compile(r"^\s*(`{3,}|\$\$)")
CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1")


def render(md: str) -> str:
    meta, body = _split_front_matter(md)
    body, sources = _pop_definitions(body)
    body = _link_citations(body, set(sources))

    parser = _parser()
    tokens = parser.parse(body)
    _set_heading_ids(tokens)
    content = parser.renderer.render(tokens, parser.options, {})
    content = _external_links_new_tab(content)
    if sources:
        items = "\n".join(
            f'<li id="src-{n}" value="{n}">{_external_links_new_tab(parser.renderInline(text))}</li>'
            for n, text in sources.items()
        )
        content += f'\n<ol class="sources">\n{items}\n</ol>\n'

    title = meta.get("title") or "Gemini Deep Research report"
    return _page(title, meta, _toc(tokens), content)


def _parser() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"html": True})
        .enable("table")
        .enable("strikethrough")
        .use(dollarmath_plugin, double_inline=False)
    )


def _split_front_matter(md: str) -> tuple[dict, str]:
    if not md.startswith("---\n"):
        return {}, md
    head, body = md[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        key, _, value = line.partition(": ")
        try:
            meta[key] = json.loads(value)
        except json.JSONDecodeError:
            meta[key] = value
    return meta, body


def _pop_definitions(body: str) -> tuple[str, dict[int, str]]:
    kept, sources = [], {}
    for line in body.splitlines():
        m = DEF_RE.match(line)
        if m:
            sources[int(m.group(1))] = m.group(2)
        else:
            kept.append(line)
    return "\n".join(kept), sources


def _link_citations(body: str, known: set[int]) -> str:
    def cite(m: re.Match) -> str:
        n = int(m.group(1))
        if n in known:
            return f'<sup class="cite"><a href="#src-{n}">{n}</a></sup>'
        return f'<sup class="cite">{n}</sup>'

    def outside_code(line: str) -> str:
        parts = CODE_SPAN_RE.split(line)
        # split yields [text, ticks, code, text, ticks, code, ...]
        out = []
        for i, part in enumerate(parts):
            kind = i % 3
            if kind == 0:
                out.append(REF_RE.sub(cite, part))
            elif kind == 1:
                out.append(part)
            else:
                out.append(part + parts[i - 1])
        return "".join(out)

    lines, fence = [], None
    for line in body.splitlines():
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1)
        elif fence is not None and line.strip() == fence:
            fence = None
        elif fence is None:
            line = outside_code(line)
        lines.append(line)
    return "\n".join(lines)


def _external_links_new_tab(content: str) -> str:
    return re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', content)


def _heading_text(inline, math: bool = False) -> str:
    """Text and code (and TeX if math) of a heading, skipping injected citation markup."""
    kinds = ("text", "code_inline", "math_inline") if math else ("text", "code_inline")
    out, in_cite = [], False
    for child in inline.children:
        if child.type == "html_inline":
            in_cite = child.content.startswith('<sup class="cite"') or (in_cite and child.content != "</sup>")
        elif child.type in kinds and not in_cite:
            out.append(child.content)
    return "".join(out)


def _set_heading_ids(tokens) -> None:
    slugs: set[str] = set()
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag in ("h1", "h2", "h3", "h4"):
            tok.attrSet("id", unique_slug(slugify(_heading_text(tokens[i + 1])), slugs))


def _toc(tokens) -> str:
    items = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag in ("h2", "h3"):
            text = _heading_text(tokens[i + 1], math=True)
            if tok.tag == "h2" and text.startswith("Sources"):
                continue
            items.append(f'<li class="toc-{tok.tag}"><a href="#{tok.attrs["id"]}">{html.escape(text)}</a></li>')
    return '<nav class="toc"><strong>Contents</strong><ul>' + "".join(items) + "</ul></nav>" if items else ""


@lru_cache(maxsize=1)
def _katex_css() -> str:
    css = (KATEX / "katex.min.css").read_text(encoding="utf-8")

    def font_src(m: re.Match) -> str:
        name = m.group(1)
        data = base64.b64encode((KATEX / "fonts" / f"{name}.woff2").read_bytes()).decode("ascii")
        return f'src:url(data:font/woff2;base64,{data}) format("woff2")'

    return re.sub(r"src:url\(fonts/([\w-]+)\.woff2\) format\(\"woff2\"\)[^;}]*", font_src, css)


@lru_cache(maxsize=1)
def _katex_js() -> str:
    return (KATEX / "katex.min.js").read_text(encoding="utf-8").replace("</script", "<\\/script")


def _page(title: str, meta: dict, toc: str, content: str) -> str:
    esc = html.escape
    source = meta.get("source_url")
    info = []
    if source:
        info.append(f'Source: <a href="{esc(source)}" target="_blank" rel="noopener">{esc(source)}</a>')
    if meta.get("captured_at"):
        info.append(f"Captured: {esc(meta['captured_at'])}")
    header = f'<header class="meta">{" &middot; ".join(info)}</header>' if info else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{_katex_css()}</style>
<style>{(ASSETS / "report.css").read_text(encoding="utf-8")}</style>
</head>
<body>
{header}
<div class="layout">
{toc}
<main>
{content}
</main>
</div>
<script>{_katex_js()}</script>
<script>
document.querySelectorAll(".math.inline, .math.block").forEach(function (el) {{
  try {{
    katex.render(el.textContent, el, {{displayMode: el.classList.contains("block"), throwOnError: false}});
  }} catch (e) {{ el.title = String(e); }}
}});
</script>
</body>
</html>
"""
