import json

from gemini_research.cli import main

from .conftest import LIVE


def test_convert_writes_outputs(tmp_path):
    assert main(["convert", str(LIVE), "-o", str(tmp_path)]) == 0
    assert (tmp_path / "report.md").read_text(encoding="utf-8").startswith("---\n")
    assert (tmp_path / "report.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["counts"] == {"headings": 33, "citations": 286, "sources_used": 47, "sources_unused": 58,
                              "display_math": 12}


def test_convert_missing_report(tmp_path):
    raw = tmp_path / "raw.html"
    raw.write_text("<html><body>nothing</body></html>", encoding="utf-8")
    assert main(["convert", str(raw)]) == 1


def test_fetch_rejects_non_conversation_url(capsys):
    assert main(["fetch", "https://gemini.google.com/app?x=1"]) == 1
    assert "Not a Gemini conversation URL" in capsys.readouterr().err
