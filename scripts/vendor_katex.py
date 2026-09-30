"""Download a pinned KaTeX release into gemini_research/assets/katex/."""

import io
import sys
import tarfile
import urllib.request
from pathlib import Path

VERSION = "0.16.11"
URL = f"https://registry.npmjs.org/katex/-/katex-{VERSION}.tgz"
DEST = Path(__file__).resolve().parents[1] / "gemini_research" / "assets" / "katex"
KEEP = {"katex.min.js", "katex.min.css"}


def main() -> int:
    data = urllib.request.urlopen(URL, timeout=60).read()
    (DEST / "fonts").mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.name == "package/LICENSE" and member.isfile():
                (DEST / "LICENSE").write_bytes(tar.extractfile(member).read())
                continue
            name = member.name.removeprefix("package/dist/")
            if name == member.name or not member.isfile():
                continue
            if name in KEEP:
                target = DEST / Path(name).name
            elif name.startswith("fonts/") and name.endswith(".woff2"):
                target = DEST / name
            else:
                continue
            target.write_bytes(tar.extractfile(member).read())
    (DEST / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    print(f"KaTeX {VERSION} -> {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
