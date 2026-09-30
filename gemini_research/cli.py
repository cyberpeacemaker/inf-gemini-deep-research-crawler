"""Command line entry point: login, fetch, convert."""

import argparse
import logging
import re
import sys
from pathlib import Path

from gemini_research.extract import extract
from gemini_research.fetch import DEFAULT_PROFILE, FetchError, conversation_id, fetch, login, write_meta, write_raw
from gemini_research.index import write_index
from gemini_research.render import render


def convert(raw: Path, out_dir: Path, extra_meta: dict | None = None) -> dict:
    html = raw.read_text(encoding="utf-8")
    md = extract(html)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    (out_dir / "report.html").write_text(render(md), encoding="utf-8")
    meta = {
        **(extra_meta or {}),
        "raw": raw.as_posix(),
        "counts": {
            "headings": len(re.findall(r"^#{1,6} ", md, re.M)),
            "citations": len(re.findall(r"\[\^\d+\]", md)) - len(re.findall(r"^\[\^\d+\]: ", md, re.M)),
            "sources_used": len(re.findall(r"^\[\^\d+\]: ", md, re.M)),
            "sources_unused": _count_unused(md),
            "display_math": md.count("$$") // 2,
        },
    }
    write_meta(out_dir, meta)
    return meta


def _count_unused(md: str) -> int:
    if "## Sources consulted (not cited)\n" not in md:
        return 0
    section = md.split("## Sources consulted (not cited)\n", 1)[1].split("\n## ", 1)[0]
    return sum(1 for line in section.splitlines() if line.startswith("- ["))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gemini_research", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="open Chrome with the dedicated profile to sign in once")
    p_login.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    p_login.add_argument("--chrome", type=Path, help="path to chrome.exe (auto-detected by default)")

    p_fetch = sub.add_parser("fetch", help="capture a Deep Research URL and write raw.html, report.md, report.html")
    p_fetch.add_argument("url")
    p_fetch.add_argument("-o", "--out", type=Path, default=Path("out"))
    p_fetch.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    p_fetch.add_argument("--headless", action="store_true", help="hide the browser window")
    p_fetch.add_argument("--raw-only", action="store_true", help="only write raw.html")

    p_conv = sub.add_parser("convert", help="convert a saved raw.html offline")
    p_conv.add_argument("raw", type=Path)
    p_conv.add_argument("-o", "--out", type=Path, help="output directory (default: next to RAW)")

    p_index = sub.add_parser("index", help="write reports-index.html listing every report under ROOT")
    p_index.add_argument("root", type=Path, nargs="?", default=Path("out"))

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    try:
        if args.cmd == "login":
            login(args.profile, args.chrome)
            print(f"Profile saved: {args.profile}")
        elif args.cmd == "fetch":
            capture = fetch(args.url, args.profile, headless=args.headless)
            out_dir = args.out / conversation_id(args.url)
            raw = write_raw(capture, out_dir)
            print(f"raw: {raw}")
            if not args.raw_only:
                meta = convert(raw, out_dir, {"source_url": args.url})
                print(f"markdown: {out_dir / 'report.md'}\nhtml: {out_dir / 'report.html'}\ncounts: {meta['counts']}")
            try:
                print(f"index: {write_index(args.out)[0]}")
            except (ValueError, OSError) as e:
                print(f"warning: index not updated: {e}", file=sys.stderr)
        elif args.cmd == "index":
            path, n = write_index(args.root)
            print(f"index: {path} ({n} report{'' if n == 1 else 's'})")
        elif args.cmd == "convert":
            out_dir = args.out or args.raw.parent
            meta = convert(args.raw, out_dir)
            print(f"markdown: {out_dir / 'report.md'}\nhtml: {out_dir / 'report.html'}\ncounts: {meta['counts']}")
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
