"""Convert a captured Gemini Deep Research DOM into lossless markdown."""

import json
import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

log = logging.getLogger(__name__)

REPORT_SELECTOR = "#extended-response-markdown-content"
SKIP_TAGS = {"button", "mat-icon", "gem-icon", "gem-icon-button", "sources-carousel-inline", "sources-carousel",
             "script", "style", "img", "svg"}
SKIP_CLASSES = {"cdk-visually-hidden", "code-block-decoration", "katex"}
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table", "blockquote", "hr",
              "pre", "code-block", "section"}
TRANSPARENT_TAGS = {"span", "response-element", "link-block", "sup", "source-footnote", "div", "section",
                    "code-block", "thead", "tbody", "tr", "td", "th", "sub", "u", "mark"}
FENCE_LANG = {"Splunk SPL": "spl", "YAML": "yaml"}
TEXT_ESCAPE = re.compile(r"([\\*$`<])")
INLINE_MATH_RE = re.compile(r"((?<!\\)\$[^$]+?(?<!\\)\$)")


@dataclass
class Source:
    title: str
    url: str
    domain: str


def extract(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    report = soup.select_one(REPORT_SELECTOR)
    if report is None:
        raise ValueError(f"{REPORT_SELECTOR} not found")
    for comment in report.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    lists = soup.select_one("deep-research-source-lists")
    used = _sources(lists, "used-sources") if lists is not None else []
    blocks = _blocks(report)
    if not used:
        blocks = [re.sub(r"\[\^(\d+)\]", r"[\1]", b) for b in blocks]
    parts = [_front_matter(soup, report), *blocks]

    if lists is not None:
        unused = _sources(lists, "unused-sources")
        if unused:
            parts.append("## Sources consulted (not cited)")
            parts.append("\n".join(f"- {_link(s)} ({s.domain})" for s in unused))
        if used:
            parts.append("## Sources")
            parts.append("\n".join(f"[^{i}]: {_link(s)} ({s.domain})" for i, s in enumerate(used, 1)))
    return "\n\n".join(p for p in parts if p) + "\n"


# --- front matter and sources ---

def _front_matter(soup: BeautifulSoup, report: Tag) -> str:
    def meta(name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name})
        return tag["content"] if tag and tag.get("content") else None

    h1 = report.find("h1")
    fields = {
        "source_url": meta("gemini-source-url"),
        "title": _collapse(h1.get_text(" ")) if h1 else meta("gemini-page-title"),
        "page_title": meta("gemini-page-title"),
        "captured_at": meta("gemini-captured-at"),
    }
    lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items() if v]
    return "---\n" + "\n".join(lines) + "\n---" if lines else ""


def _sources(lists: Tag, cls: str) -> list[Source]:
    container = lists.select_one(f".source-list.{cls}")
    if container is None:
        return []
    out = []
    for item in container.select("browse-web-item"):
        a = item.select_one("a[href]")
        if a is None:
            log.warning("source item without link: %s", _collapse(item.get_text(" "))[:80])
            continue
        domain = item.select_one("[data-test-id=domain-name]")
        title = item.select_one("[data-test-id=sub-title]")
        domain_text = _collapse(domain.get_text(" ")) if domain else ""
        out.append(Source(title=_collapse(title.get_text(" ")) if title else domain_text or a["href"],
                          url=a["href"], domain=domain_text))
    return out


def _link(s: Source) -> str:
    text = s.title.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    url = s.url if not re.search(r"[\s()<>]", s.url) else f"<{s.url}>"
    return f"[{text}]({url})"


# --- block rendering ---

def _is_skipped(node: Tag) -> bool:
    if node.name in SKIP_TAGS:
        return True
    classes = set(node.get("class") or [])
    return bool(classes & SKIP_CLASSES) and "math-inline" not in classes and "math-block" not in classes


def _is_block(node: Tag) -> bool:
    if "math-block" in (node.get("class") or []):
        return True
    if node.name in BLOCK_TAGS:
        return True
    return node.find(BLOCK_TAGS) is not None


def _blocks(node: Tag) -> list[str]:
    out: list[str] = []
    buf: list[str] = []

    def flush():
        text = _collapse("".join(buf))
        buf.clear()
        if text:
            out.append(text)

    for child in node.children:
        if isinstance(child, NavigableString):
            buf.append(_text(child))
        elif isinstance(child, Tag) and not _is_skipped(child) and _is_block(child):
            flush()
            out.extend(_block(child))
        elif isinstance(child, Tag):
            buf.append(_inline(child))
    flush()
    return out


def _block(node: Tag) -> list[str]:
    name = node.name
    classes = node.get("class") or []
    if "math-block" in classes:
        return [f"$$\n{node['data-math'].strip()}\n$$"]
    if re.fullmatch(r"h[1-6]", name):
        return [f"{'#' * int(name[1])} {_collapse(_inline_children(node))}"]
    if name == "p":
        return _blocks(node)
    if name in ("ul", "ol"):
        return [_list(node)]
    if name == "table":
        return [_table(node)]
    if name == "code-block":
        return [_code_block(node)]
    if name == "pre":
        return [_fence(node.get_text(), "")]
    if name == "hr":
        return ["---"]
    if name == "blockquote":
        inner = "\n\n".join(_blocks(node))
        return ["\n".join("> " + l if l else ">" for l in inner.splitlines())]
    if name not in TRANSPARENT_TAGS:
        log.warning("unknown block tag <%s>, rendering children", name)
    return _blocks(node)


def _list(node: Tag) -> str:
    ordered = node.name == "ol"
    start = int(node.get("start") or 1)
    items = []
    for i, li in enumerate(node.find_all("li", recursive=False)):
        marker = f"{start + i}. " if ordered else "- "
        pad = " " * len(marker)
        parts = _blocks(li) or [""]
        body = "\n\n".join(parts)
        lines = body.splitlines() or [""]
        items.append(marker + lines[0] + "".join("\n" + (pad + l if l else "") for l in lines[1:]))
    loose = any("\n\n" in it for it in items)
    return ("\n\n" if loose else "\n").join(items)


def _table(node: Tag) -> str:
    rows = []
    for tr in node.find_all("tr"):
        cells = [_cell(td) for td in tr.find_all(["th", "td"], recursive=False)]
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _cell(td: Tag) -> str:
    parts = []
    for block in _blocks(td):
        block = re.sub(r"\$\$\n(.*?)\n\$\$", lambda m: f"${m.group(1)}$", block, flags=re.S)
        parts.append(_collapse(block.replace("\n", " ")))
    pieces = INLINE_MATH_RE.split("<br>".join(parts))
    return "".join(p.replace("|", "\\vert{}") if i % 2 else p.replace("|", "\\|") for i, p in enumerate(pieces))


def _code_block(node: Tag) -> str:
    label_el = node.select_one(".code-block-decoration span")
    label = _collapse(label_el.get_text()) if label_el else ""
    code = node.select_one("code[data-test-id=code-content]") or node.select_one("pre code") or node.select_one("pre")
    return _fence(code.get_text() if code else "", FENCE_LANG.get(label, ""))


def _fence(code: str, lang: str) -> str:
    code = code.rstrip("\n")
    longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{code}\n{ticks}"


# --- inline rendering ---

def _inline_children(node: Tag) -> str:
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(_text(child))
        elif isinstance(child, Tag):
            out.append(_inline(child))
    return "".join(out)


def _inline(node: Tag) -> str:
    if _is_skipped(node):
        return ""
    name = node.name
    classes = node.get("class") or []
    if "math-inline" in classes or "math-block" in classes:
        return f"${node['data-math'].strip()}$"
    if name == "source-footnote":
        sup = node.find("sup", attrs={"data-turn-source-index": True})
        return f"[^{sup['data-turn-source-index']}]" if sup else ""
    if name == "sup" and node.get("data-turn-source-index"):
        return f"[^{node['data-turn-source-index']}]"
    if name in ("b", "strong"):
        return _wrap("**", _inline_children(node))
    if name in ("i", "em"):
        return _wrap("*", _inline_children(node))
    if name == "code":
        return _code_span(node.get_text())
    if name == "a" and node.get("href"):
        text = _collapse(_inline_children(node)) or node["href"]
        return f"[{text}]({node['href']})"
    if name == "br":
        return "<br>"
    if name not in TRANSPARENT_TAGS:
        log.warning("unknown inline tag <%s>, rendering children", name)
    return _inline_children(node)


def _wrap(marker: str, s: str) -> str:
    core = s.strip()
    if not core:
        return s
    lead = s[: len(s) - len(s.lstrip())]
    trail = s[len(s.rstrip()):]
    return f"{' ' if lead else ''}{marker}{_collapse(core)}{marker}{' ' if trail else ''}"


def _code_span(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def _text(s: NavigableString) -> str:
    return TEXT_ESCAPE.sub(r"\\\1", re.sub(r"\s+", " ", str(s)))


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()
