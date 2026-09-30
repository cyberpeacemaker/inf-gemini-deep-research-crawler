"""Print tag inventory and structural samples of a raw capture. Usage: probe_fixture.py FILE"""

import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup, Comment

soup = BeautifulSoup(Path(sys.argv[1]).read_text(encoding="utf-8"), "lxml")
report = soup.select_one("#extended-response-markdown-content")
katex = set()
for k in report.select(".katex, .katex-display"):
    katex.update(id(n) for n in k.find_all(True))
tags = Counter(t.name for t in report.find_all(True) if id(t) not in katex)
print("tags (excluding katex internals):")
for name, n in tags.most_common():
    print(f"  {n:5} {name}")

print("\ndirect children of report:", Counter(c.name for c in report.find_all(True, recursive=False)))
for name in ["link-block", "blockquote", "hr", "ol", "ul", "img", "a", "i", "em", "strong", "code-block"]:
    el = report.find(name)
    if el:
        print(f"\n--- first <{name}> (parent {el.parent.name}) ---")
        print(str(el)[:900])

nested = [li for li in report.select("li") if li.find(["ul", "ol"])]
print("\nnested lists:", len(nested))
print("math in tables:", len(report.select("table [data-math]")))
print("math-block count:", len(report.select(".math-block")), "inline:", len(report.select(".math-inline")))
print("li containing p:", len(report.select("li > p")))

src = soup.select_one("deep-research-source-lists")
if src:
    item = src.select_one("browse-web-item")
    print("\n--- first browse-web-item ---")
    print(str(item)[:2500])
    for lst in src.select(".source-list"):
        print(lst.get("class"), len(lst.select("browse-web-item")))
    heads = [h.get_text(" ", strip=True) for h in src.find_all(["h1", "h2", "h3", "h4", "div"], class_=lambda c: c and "title" in " ".join(c) if isinstance(c, list) else c and "title" in c)][:10]
    print("title-ish:", heads)
