import re
from collections import Counter

from bs4 import BeautifulSoup

from gemini_research.extract import extract

UI_STRINGS = ["Learn More", "Code snippet", "Download code", "Copy code", "Opens in a new window"]
LEAKS = ["katex", "hljs", "source-footnote", "sources-carousel", "<!--", "&lt;", "&gt;", "&amp;", "Learn More",
         "Download code", "Copy code", "mat-icon", "data-path-to-node"]
LIVE_H1 = ("Passive Network Detection of Port Scans and Host Sweeps: An Analytical Review of Telemetry, "
           "Statistical Scoring, and Operational Trade-Offs")


def outside_fences(md: str) -> list[str]:
    lines, fence = [], None
    for line in md.splitlines():
        m = re.match(r"^(`{3,}|\$\$)", line)
        if fence is None and m:
            fence = m.group(1)
            continue
        if fence is not None:
            if line.strip() == fence:
                fence = None
            continue
        lines.append(line)
    return lines


def ref_count(md: str) -> int:
    return len(re.findall(r"\[\^\d+\]", md)) - len(re.findall(r"^\[\^\d+\]: ", md, re.M))


def body(md: str) -> str:
    """Markdown without front matter."""
    return md.split("\n---\n", 1)[1] if md.startswith("---\n") else md


def heading_counts(md: str) -> Counter:
    return Counter(len(m.group(1)) for line in outside_fences(body(md)) if (m := re.match(r"^(#{1,6}) ", line)))


def expected_words(html: str) -> Counter:
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("#extended-response-markdown-content")
    for m in node.select("[data-math]"):
        m.clear()
        m.append(m["data-math"])
    for junk in node.select("button, mat-icon, sources-carousel-inline, .code-block-decoration, .cdk-visually-hidden"):
        junk.decompose()
    text = node.get_text(" ")
    for ui in UI_STRINGS:
        text = text.replace(ui, " ")
    return Counter(re.findall(r"\w+", text))


# --- live fixture (signed-in capture; conversation URL is a placeholder) ---

def test_front_matter(live_md):
    head = live_md.split("\n---\n", 1)[0]
    assert live_md.startswith("---\n")
    assert "source_url: \"https://gemini.google.com/app/example" in head
    assert f"title: \"{LIVE_H1}\"" in head
    assert "captured_at: " in head


def test_live_headings(live_md):
    assert f"\n# {LIVE_H1}\n" in live_md
    counts = heading_counts(live_md)
    assert (counts[1], counts[2], counts[3], counts[4]) == (1, 8 + 2, 19, 3)


def test_live_tables(live_md):
    separators = [l for l in live_md.splitlines() if re.fullmatch(r"\|( --- \|)+", l)]
    assert len(separators) == 9
    assert "<p>" not in live_md


def test_live_math(live_html, live_md):
    soup = BeautifulSoup(live_html, "lxml")
    inline = [m["data-math"] for m in soup.select("#extended-response-markdown-content .math-inline")]
    display = [m["data-math"] for m in soup.select("#extended-response-markdown-content .math-block")]
    assert (len(inline), len(display)) == (104, 12)
    for tex in inline:
        assert f"${tex}$" in live_md, tex
    dedented = re.sub(r"^ +", "", live_md, flags=re.M)
    for tex in display:
        assert f"$$\n{tex}\n$$" in dedented, tex


def test_live_code_fence(live_md):
    fences = [l for l in live_md.splitlines() if re.match(r"^`{3,}\S*$", l)]
    assert len(fences) == 2
    assert "alert tcp $EXTERNAL_NET any -> $HOME_NET 3127" in live_md


def test_live_citations(live_md):
    assert ref_count(live_md) == 286
    defs = re.findall(r"^\[\^(\d+)\]: ", live_md, re.M)
    assert defs == [str(i) for i in range(1, 48)]
    line = next(l for l in live_md.splitlines() if l.startswith("[^2]: "))
    assert "(https://www.icir.org/vern/papers/portscan-oak04.pdf)" in line
    assert "Fast Portscan Detection Using Sequential Hypothesis Testing" in line
    assert "(icir.org)" in line


def test_live_unused_sources(live_md):
    section = live_md.split("## Sources consulted (not cited)\n", 1)[1].split("\n## ", 1)[0]
    items = [l for l in section.splitlines() if l.startswith("- [")]
    assert len(items) == 58


def test_live_sources_last(live_md):
    assert live_md.index("## Sources consulted (not cited)") < live_md.index("\n## Sources\n")
    assert live_md.rstrip().splitlines()[-1].startswith("[^47]: ")


def test_live_link_blocks(live_md):
    for url in ["https://www.unb.ca/cic/datasets/ids-2017.html", "https://www.unb.ca/cic/datasets/ids-2018.html",
                "https://wiki.wireshark.org/SampleCaptures", "https://mawi.wide.ad.jp/mawi/"]:
        assert f"]({url})" in live_md


def test_live_lists(live_md):
    assert "1. **Packet Sampling Asymmetry in Flow Records:** High-throughput" in live_md
    assert re.search(r"^- If \$S_N \\ge \\ln\(B\)\$", live_md, re.M)
    assert re.search(r"^ {2,}- ", live_md, re.M), "nested list lost"


def test_live_no_word_loss(live_html, live_md):
    missing = expected_words(live_html) - Counter(re.findall(r"\w+", live_md))
    assert not missing, dict(list(missing.items())[:20])


def prose(md: str) -> str:
    """Report prose only: no fences, no source sections."""
    text = "\n".join(outside_fences(body(md)))
    return re.split(r"^## Sources", text, flags=re.M)[0]


def test_live_no_ui_leak(live_md):
    for leak in LEAKS:
        assert leak not in prose(live_md), leak


def test_live_citation_indexes_resolve(live_html, live_md):
    soup = BeautifulSoup(live_html, "lxml")
    used = soup.select("deep-research-source-lists .used-sources browse-web-item")
    idx = {int(s["data-turn-source-index"]) for s in soup.select("#extended-response-markdown-content sup[data-turn-source-index]")}
    assert min(idx) >= 1 and max(idx) <= len(used)
    defined = {int(n) for n in re.findall(r"^\[\^(\d+)\]: ", live_md, re.M)}
    assert idx <= defined


def test_live_source_urls_are_direct(live_md):
    defs = re.findall(r"^\[\^\d+\]: .*$", live_md, re.M)
    assert defs and not any("google.com/url" in d for d in defs)


def test_no_warnings_on_fixtures(live_html, nosources_html, caplog):
    with caplog.at_level("WARNING", logger="gemini_research.extract"):
        extract(live_html)
        extract(nosources_html)
    assert not caplog.records, [r.getMessage() for r in caplog.records]


def test_prose_escaping():
    html = ('<div id="extended-response-markdown-content"><p>costs $5 and $10 * 2 via `x` &lt;tag&gt;</p>'
            '<table><tr><th>a</th></tr><tr><td>x | y <span class="math-inline" data-math="|x|"></span></td></tr>'
            '</table></div>')
    md = extract(html)
    assert "costs \\$5 and \\$10 \\* 2 via \\`x\\` \\<tag>" in md
    assert "| x \\| y $\\vert{}x\\vert{}$ |" in md


# --- synthetic fixture (report node only, no source list) ---

def test_no_source_list_uses_plain_markers(nosources_md):
    assert "Field notes[1]. More notes[2]." in nosources_md
    assert "[^" not in nosources_md
    assert "## Sources" not in nosources_md
    assert "http://" not in nosources_md and "https://" not in nosources_md


def test_wrapper_document_same_output(nosources_html, nosources_md):
    wrapped = f"<html><body><nav>Sign in</nav>{nosources_html}<footer>x</footer></body></html>"
    assert extract(wrapped) == nosources_md
