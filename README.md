# gemini-research

Export a Gemini Deep Research report, given its URL, to:

- `report.md`: lossless markdown for agents. It has front matter, headings, tables, fenced code, `$`/`$$` LaTeX, in-place `[^N]` citations, and a `## Sources` footnote list with the real URLs.
- `report.html`: one self-contained offline page for people. KaTeX is inlined, and the page has a table of contents, clickable citations, and light/dark themes. It makes no network requests.
- `raw.html`: the captured report node plus the source lists, so the conversion can be rerun offline.
- `meta.json`: `written_at`, the path to `raw`, and `counts`. `fetch` also records `source_url`. Capture time is `captured_at` in the markdown front matter.

Project page: [docs/index.html](docs/index.html), a single offline file with the pipeline, outputs, DOM mapping, CLI, and tests.

Sample output: [examples/network-scans/report.md](examples/network-scans/report.md) and [report.html](examples/network-scans/report.html). Download the HTML and open it locally to see it rendered.

This is an unofficial exporter. Gemini's DOM can change and break the selectors below. Automating a signed-in Google session may conflict with Google's terms; use it on your own account.

Gemini only serves the report to a signed-in browser. Signed out, `https://gemini.google.com/app/<id>` redirects to `/app`, so a plain HTTP fetch cannot work.

## Setup

Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

On macOS or Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe` here and in the commands below.

This needs Google Chrome installed. Playwright drives it through `channel="chrome"`. `login` looks for Chrome in the standard Windows and macOS install paths and at `/usr/bin/google-chrome`. Pass `--chrome PATH` if yours is somewhere else.

## Usage

```powershell
# One time: opens plain Chrome on a dedicated profile (%USERPROFILE%\.gemini-research\profile).
# Sign in to Google, then close the window.
.\.venv\Scripts\python.exe -m gemini_research login

# Capture and convert. Writes out\<conversation-id>\{raw.html,report.md,report.html,meta.json}
.\.venv\Scripts\python.exe -m gemini_research fetch "https://gemini.google.com/app/<conversation-id>"

# Re-convert a saved capture offline
.\.venv\Scripts\python.exe -m gemini_research convert out\<conversation-id>\raw.html

# Rebuild the report index (fetch does this automatically)
.\.venv\Scripts\python.exe -m gemini_research index
```

### Report index

`out\reports-index.html` lists every report under `out\`, newest first. Each entry shows a readable title (the Gemini page title without the " - Google Gemini" suffix) that links to its `report.html`, followed by the full report title, the conversation id, the capture date, the number of cited sources and a link to the Gemini conversation. `fetch` refreshes it after each capture. After `convert`, run `index` yourself. Pass a path to index a different output root. `out\` is gitignored, so the index and the reports stay on your machine; move or zip `out\` as a whole to keep the links working.

`fetch` exit codes:

- `0`: success.
- `1`: bad URL, or the report was not found.
- `2`: not signed in. Run `login`.

Add `--headless` to hide the window, and `--raw-only` to skip the conversion.

The profile directory holds your Google session cookies. It is outside the repo on purpose, so do not commit it.

## How the capture maps to markdown

- The report prose is in `#extended-response-markdown-content`. The bibliography is in the sibling `deep-research-source-lists`: `.used-sources` for cited sources and `.unused-sources` for sources consulted but not cited.
- Each citation is an empty `sup[data-turn-source-index=N]`. N points to entry N of the used-sources list, counting from 1. It becomes `[^N]`, and `[^N]: [title](url) (domain)` is added under `## Sources`. If a capture has no source list, markers become plain `[N]` and no URLs are invented.
- Math comes from the `data-math` attribute (entity-decoded). The KaTeX markup is dropped.
- Code comes from `pre code[data-test-id=code-content]`. The labels `Splunk SPL` and `YAML` map to the `spl` and `yaml` fence tags; other labels get no tag.
- Carousels, buttons, icons, images, SVGs, and screen-reader-only text are dropped. Any unknown tag is rendered through its children and logs a warning.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Fixtures:

- `tests/fixtures/network-scans.raw.html`: a signed-in capture with a source list. The conversation URL stored in it is a placeholder.
- `tests/fixtures/no-source-list.raw.html`: a small synthetic capture of the report node only, with no source list.

The tests check:

- Heading, table, math, code, citation, and source counts.
- That every word of the report's visible text appears in the markdown.
- That no UI text leaks into the output.
- That the HTML is fully offline.
- That signed-out, missing-report, and ready pages are classified correctly.

## Maintenance scripts

- `scripts/vendor_katex.py`: re-downloads the pinned KaTeX 0.16.11 build into `gemini_research/assets/katex/`. KaTeX is MIT; its license is `gemini_research/assets/katex/LICENSE`.
- `scripts/save_cdp_capture.py`: saves a DevTools `Runtime.evaluate` result of `fetch.CAPTURE_JS` as a fixture.
- `scripts/probe_fixture.py`: prints the tag inventory of a capture. Run it when Gemini's DOM changes.

## License

MIT. See [LICENSE](LICENSE). KaTeX is vendored under its own MIT license.
