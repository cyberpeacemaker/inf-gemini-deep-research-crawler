from pathlib import Path

import pytest

from gemini_research.extract import extract

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "tests" / "fixtures" / "network-scans.raw.html"
NOSOURCES = ROOT / "tests" / "fixtures" / "no-source-list.raw.html"


@pytest.fixture(scope="session")
def live_html() -> str:
    return LIVE.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def nosources_html() -> str:
    return NOSOURCES.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def live_md(live_html) -> str:
    return extract(live_html)


@pytest.fixture(scope="session")
def nosources_md(nosources_html) -> str:
    return extract(nosources_html)
