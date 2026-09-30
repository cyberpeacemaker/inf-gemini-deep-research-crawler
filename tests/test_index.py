import json
import re

from bs4 import BeautifulSoup

from gemini_research.cli import main
from gemini_research.index import collect, render_index, write_index


def topic(root, cid, captured_at="2026-09-30T08:00:00Z", title="Full Title", page_title="Short - Google Gemini",
          meta=True):
    d = root / cid
    d.mkdir()
    head = [f"source_url: {json.dumps('https://gemini.google.com/app/' + cid)}"]
    if title is not None:
        head.append(f"title: {json.dumps(title)}")
    if page_title is not None:
        head.append(f"page_title: {json.dumps(page_title)}")
    head.append(f"captured_at: {json.dumps(captured_at)}")
    (d / "report.md").write_text("---\n" + "\n".join(head) + "\n---\n\n# x\n", encoding="utf-8")
    if meta:
        (d / "meta.json").write_text(json.dumps({"counts": {"sources_used": 7, "headings": 3}}), encoding="utf-8")
    return d


def soup_of(root):
    return BeautifulSoup(write_index(root)[0].read_text(encoding="utf-8"), "lxml")


def test_entries_newest_first(tmp_path):
    topic(tmp_path, "aaa", "2026-09-01T00:00:00Z", page_title="Old - Google Gemini")
    topic(tmp_path, "bbb", "2026-09-30T00:00:00Z", page_title="New - Google Gemini")
    soup = soup_of(tmp_path)
    items = soup.select("li.topic")
    assert [li.h2.get_text(strip=True) for li in items] == ["New", "Old"]
    assert items[0].h2.a["href"] == "bbb/report.html"
    assert "bbb" in items[0].get_text()
    assert "7 sources" in items[0].get_text()
    assert items[0].select_one('a[href="https://gemini.google.com/app/bbb"]')


def test_title_fallbacks(tmp_path):
    topic(tmp_path, "t1", page_title=None, title="Only Title")
    topic(tmp_path, "t2", page_title=None, title=None)
    titles = {e["id"]: e["label"] for e in collect(tmp_path)}
    assert titles == {"t1": "Only Title", "t2": "t2"}


def test_skips_bad_and_tolerates_missing(tmp_path):
    (tmp_path / "noreport").mkdir()
    bad = tmp_path / "broken"
    bad.mkdir()
    (bad / "report.md").write_text("---\ntitle: x\nno close\n", encoding="utf-8")
    topic(tmp_path, "nometa", meta=False)
    topic(tmp_path, "nodate", captured_at=None)
    ids = [e["id"] for e in collect(tmp_path)]
    assert ids == ["nometa", "nodate"]


def test_empty_root(tmp_path):
    assert "No reports found" in write_index(tmp_path)[0].read_text(encoding="utf-8")


def test_escaping_and_url_encoding(tmp_path):
    topic(tmp_path, "has space", page_title="</script><script>alert(1)")
    page = render_index(collect(tmp_path))
    assert "<script" not in page
    soup = BeautifulSoup(page, "lxml")
    assert soup.select_one("li.topic h2 a")["href"] == "has%20space/report.html"


def test_offline(tmp_path):
    topic(tmp_path, "aaa")
    soup = soup_of(tmp_path)
    assert not soup.select("link[href], script[src]")
    for style in soup.find_all("style"):
        assert not re.search(r"url\(", style.get_text())


def test_cli_index(tmp_path, capsys):
    topic(tmp_path, "aaa")
    assert main(["index", str(tmp_path)]) == 0
    assert (tmp_path / "reports-index.html").exists()
    assert "1 report" in capsys.readouterr().out
