"""Write reports-index.html: one offline page linking every report under an output root."""

import html
import json
import logging
from pathlib import Path
from urllib.parse import quote

from gemini_research.render import ASSETS, _split_front_matter

log = logging.getLogger(__name__)
INDEX_NAME = "reports-index.html"
GEMINI_SUFFIX = " - Google Gemini"

CSS = """
main.index { max-width: 860px; margin: 0 auto; padding: 24px; }
ul.topics { list-style: none; padding: 0; }
li.topic { padding: 14px 0; border-bottom: 1px solid var(--border); }
li.topic h2 { margin: 0 0 4px; border: 0; padding: 0; font-size: 1.2em; }
li.topic h2 a { text-decoration: none; }
li.topic .full { margin: 0 0 4px; }
li.topic .info, li.topic .full { font-size: 13px; color: var(--muted); overflow-wrap: anywhere; }
"""


def collect(root: Path) -> list[dict]:
    entries = []
    for md_path in sorted(root.glob("*/report.md")):
        folder = md_path.parent
        try:
            meta, _ = _split_front_matter(md_path.read_text(encoding="utf-8"))
            counts = {}
            if (folder / "meta.json").exists():
                counts = json.loads((folder / "meta.json").read_text(encoding="utf-8")).get("counts", {})
        except (ValueError, OSError) as e:  # JSONDecodeError is a ValueError
            log.warning("skipping %s: %s", folder, e)
            continue
        page_title = meta.get("page_title") or ""
        if page_title.endswith(GEMINI_SUFFIX):
            page_title = page_title[: -len(GEMINI_SUFFIX)]
        title = meta.get("title") or ""
        entries.append({
            "id": folder.name,
            "label": page_title or title or folder.name,
            "title": title,
            "source_url": meta.get("source_url"),
            "captured_at": meta.get("captured_at"),
            "counts": counts,
        })
    entries.sort(key=lambda e: e["captured_at"] or "", reverse=True)
    return entries


def render_index(entries: list[dict]) -> str:
    esc = html.escape
    items = []
    for e in entries:
        info = [f"<code>{esc(e['id'])}</code>"]
        if e["captured_at"]:
            info.append(esc(e["captured_at"][:10]))
        if "sources_used" in e["counts"]:
            info.append(f"{e['counts']['sources_used']} sources")
        if e["source_url"]:
            info.append(f'<a href="{esc(e["source_url"])}" target="_blank" rel="noopener">Gemini</a>')
        full = f'<p class="full">{esc(e["title"])}</p>' if e["title"] and e["title"] != e["label"] else ""
        items.append(
            f'<li class="topic"><h2><a href="{quote(e["id"])}/report.html">{esc(e["label"])}</a></h2>'
            f'{full}<div class="info">{" &middot; ".join(info)}</div></li>'
        )
    body = f'<ul class="topics">{"".join(items)}</ul>' if items else "<p>No reports found.</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gemini Deep Research reports</title>
<style>{(ASSETS / "report.css").read_text(encoding="utf-8")}{CSS}</style>
</head>
<body>
<main class="index">
<h1>Gemini Deep Research reports</h1>
<p class="info">{len(entries)} report{"" if len(entries) == 1 else "s"}</p>
{body}
</main>
</body>
</html>
"""


def write_index(root: Path) -> tuple[Path, int]:
    entries = collect(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / INDEX_NAME
    path.write_text(render_index(entries), encoding="utf-8")
    return path, len(entries)
