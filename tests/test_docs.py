import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "index.html"


def _page():
    html = PAGE.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="page-data">(.*?)</script>', html, re.S)
    assert m, "page-data block missing"
    return html, json.loads(m.group(1))


def test_sample_counts_match_example_meta():
    _, data = _page()
    meta = json.loads((ROOT / "examples" / "network-scans" / "meta.json").read_text(encoding="utf-8"))
    assert data["sample"]["counts"] == meta["counts"]


def test_test_counts_match_suite():
    _, data = _page()
    actual = {
        p.name: len(re.findall(r"^def test_", p.read_text(encoding="utf-8"), re.M))
        for p in (ROOT / "tests").glob("test_*.py")
    }
    assert {t["name"]: t["count"] for t in data["tests"]} == actual


def test_cli_matches_parser():
    _, data = _page()
    src = (ROOT / "gemini_research" / "cli.py").read_text(encoding="utf-8")
    for cmd in data["cmds"]:
        assert f'add_parser("{cmd["name"]}"' in src
        for flag in cmd["flags"]:
            for tok in re.findall(r"--?[a-z][a-z-]*", flag["k"]):
                assert f'"{tok}"' in src, tok


def test_every_subcommand_is_listed():
    _, data = _page()
    src = (ROOT / "gemini_research" / "cli.py").read_text(encoding="utf-8")
    parsers = re.findall(r'add_parser\("([a-z]+)"', src)
    assert sorted(c["name"] for c in data["cmds"]) == sorted(parsers)


def test_index_output_is_listed():
    from gemini_research.index import INDEX_NAME

    _, data = _page()
    assert f"out/{INDEX_NAME}" in [o["path"] for o in data["outputs"]]
    assert "index" in [s["name"].lower() for s in data["stages"]]


def test_page_is_self_contained():
    html, _ = _page()
    assert not re.search(r"<script[^>]+src=", html)
    assert not re.search(r"<link[^>]+stylesheet", html)
    assert not re.search(r"""url\(\s*['"]?https?:""", html)
