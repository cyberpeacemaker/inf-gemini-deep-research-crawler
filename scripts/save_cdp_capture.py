"""Write the HTML string from a saved CDP Runtime.evaluate response to a file.

Usage: python scripts/save_cdp_capture.py CDP_RESPONSE.json OUT.html
"""

import json
import sys
from pathlib import Path


def main() -> int:
    src, dest = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(src.read_text(encoding="utf-8"))
    html = data["result"]["value"]
    if not html:
        print("capture returned null: report node missing", file=sys.stderr)
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    print(f"{len(html)} chars -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
