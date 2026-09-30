"""Capture a Gemini Deep Research report from a signed-in browser profile."""

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPORT_SELECTOR = "#extended-response-markdown-content"
DEFAULT_PROFILE = Path.home() / ".gemini-research" / "profile"
CONVERSATION_RE = re.compile(r"^/app/([0-9a-f]{8,})")

CAPTURE_JS = """() => {
  const report = document.querySelector('#extended-response-markdown-content');
  if (!report) return null;
  const sources = document.querySelector('deep-research-source-lists');
  const esc = s => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  return '<!DOCTYPE html>\\n<html><head><meta charset="utf-8">'
    + '<meta name="gemini-source-url" content="' + esc(location.href) + '">'
    + '<meta name="gemini-page-title" content="' + esc(document.title) + '">'
    + '<meta name="gemini-captured-at" content="' + new Date().toISOString() + '">'
    + '</head><body>\\n' + report.outerHTML + '\\n'
    + (sources ? sources.outerHTML : '') + '\\n</body></html>\\n';
}"""


class FetchError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


@dataclass
class Capture:
    url: str
    html: str


def conversation_id(url: str) -> str | None:
    match = CONVERSATION_RE.match(urlparse(url).path)
    return match.group(1) if match else None


def classify_page(final_url: str, html: str) -> str:
    """Return 'ready', 'signed_out', or 'missing_report'."""
    if 'id="extended-response-markdown-content"' in html:
        return "ready"
    if conversation_id(final_url) is None:
        return "signed_out"
    if re.search(r'aria-label="Sign in"|>\s*Sign in\s*<', html):
        return "signed_out"
    return "missing_report"


SOURCES_READY_JS = """() => {
  const used = document.querySelectorAll('deep-research-source-lists .used-sources browse-web-item a[href]').length;
  const idx = [...document.querySelectorAll('#extended-response-markdown-content sup[data-turn-source-index]')]
    .map(s => +s.getAttribute('data-turn-source-index'));
  return idx.length === 0 || used >= Math.max(...idx);
}"""
SETTLED_JS = """() => {
  if (!/^\\/app\\/[0-9a-f]{8,}/.test(location.pathname)) return true;
  const r = document.querySelector('#extended-response-markdown-content');
  return !!r && r.getAttribute('aria-busy') === 'false';
}"""
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/usr/bin/google-chrome"),
]


def find_chrome() -> Path:
    for path in CHROME_PATHS:
        if path.exists():
            return path
    raise FetchError("Google Chrome not found. Install Chrome or pass --chrome PATH")


def login(profile: Path = DEFAULT_PROFILE, chrome: Path | None = None) -> None:
    """Open plain Chrome (no automation flags, so Google allows sign-in) on the dedicated profile."""
    import subprocess

    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([str(chrome or find_chrome()), f"--user-data-dir={profile}", "--no-first-run",
                             "https://gemini.google.com/app"])
    print("Sign in to Google in the Chrome window, then close that window.")
    proc.wait()


def fetch(url: str, profile: Path = DEFAULT_PROFILE, headless: bool = False, timeout_s: int = 120) -> Capture:
    if conversation_id(url) is None:
        raise FetchError(f"Not a Gemini conversation URL: {url}")
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright

    if not profile.exists():
        raise FetchError(f"Profile {profile} does not exist. Run: python -m gemini_research login", 2)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), channel="chrome", headless=headless,
                                                   ignore_default_args=["--enable-automation"])
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_function(SETTLED_JS, timeout=timeout_s * 1000)
            except PWTimeout:
                pass
            state = classify_page(page.url, page.content())
            if state == "signed_out":
                raise FetchError("Not signed in. Run: python -m gemini_research login", 2)
            if state != "ready":
                raise FetchError(f"Report node not found at {page.url} (state: {state})")
            page.wait_for_selector(REPORT_SELECTOR + '[aria-busy="false"]', timeout=timeout_s * 1000)
            try:
                page.wait_for_function(SOURCES_READY_JS, timeout=30000)
            except PWTimeout:
                print("warning: source list does not cover every citation index; capturing anyway", file=sys.stderr)
            html = page.evaluate(CAPTURE_JS)
        finally:
            ctx.close()
    if not html:
        raise FetchError("Report node disappeared before capture")
    return Capture(url=url, html=html)


def write_raw(capture: Capture, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "raw.html"
    path.write_text(capture.html, encoding="utf-8")
    return path


def write_meta(out_dir: Path, meta: dict) -> Path:
    path = out_dir / "meta.json"
    meta = {"written_at": datetime.now(timezone.utc).isoformat(), **meta}
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
