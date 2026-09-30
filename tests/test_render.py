import re

import pytest
from bs4 import BeautifulSoup

from gemini_research.render import render


@pytest.fixture(scope="module")
def live_page(live_md):
    return render(live_md)


@pytest.fixture(scope="module")
def nosources_page(nosources_md):
    return render(nosources_md)


def test_offline(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    assert not soup.select("link[href], script[src]")
    for style in soup.find_all("style"):
        assert not re.search(r"url\((?!data:)", style.get_text()), "external url() in CSS"


def test_katex_inlined(live_page):
    assert ".katex{" in live_page or ".katex {" in live_page
    assert "data:font/woff2;base64," in live_page
    assert "katex.render(" in live_page


def test_math_nodes(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    assert len(soup.select(".math.inline")) == 104
    assert len(soup.select(".math.block")) == 12


def test_title_and_meta(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    assert soup.title.get_text().startswith("Passive Network Detection of Port Scans")
    assert soup.select_one('a[href^="https://gemini.google.com/app/example"]')


def test_toc(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    toc = soup.select("nav.toc a[href^='#']")
    assert len(toc) >= 8 + 19
    for a in toc:
        assert soup.find(id=a["href"][1:]), a["href"]


def test_citations_link_to_sources(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    cites = soup.select("sup.cite a")
    assert len(cites) == 286
    for a in cites:
        assert soup.find(id=a["href"][1:]), a["href"]
    src = soup.find(id="src-2")
    assert src.select_one('a[href="https://www.icir.org/vern/papers/portscan-oak04.pdf"]')
    assert len(soup.select("ol.sources > li")) == 47


def test_tables_and_code(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    assert len(soup.select("table")) == 9
    assert "alert tcp $EXTERNAL_NET" in soup.select_one("pre code").get_text()


def test_external_links_new_tab(live_page):
    soup = BeautifulSoup(live_page, "lxml")
    for a in soup.select("main a[href^='http']"):
        assert a.get("target") == "_blank", a["href"]


def test_toc_strips_citations():
    md = "# T\n\n## Heading one[^1]\n\n## Rate $\\lambda$\n\ntext\n\n[^1]: [s](https://x.y)\n"
    soup = BeautifulSoup(render(md), "lxml")
    links = soup.select("nav.toc a")
    assert [a.get_text() for a in links] == ["Heading one", "Rate \\lambda"]
    assert links[0]["href"] == "#heading-one"
    assert soup.find(id="heading-one").select_one("sup.cite a[href='#src-1']")


def test_citations_without_sources(nosources_page):
    soup = BeautifulSoup(nosources_page, "lxml")
    assert "Field notes[1]" in soup.get_text()
    assert not soup.select("sup.cite")
    assert not soup.select("ol.sources")
