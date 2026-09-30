from gemini_research.fetch import classify_page, conversation_id

REPORT = '<div id="extended-response-markdown-content" aria-busy="false"><h1>T</h1></div>'
SIGNED_OUT = '<html><body><button aria-label="Sign in">Sign in</button><h1>Meet Gemini</h1></body></html>'


def test_conversation_id():
    assert conversation_id("https://gemini.google.com/app/abcdef0123456789?utm_source=x") == "abcdef0123456789"
    assert conversation_id("https://gemini.google.com/app?utm_source=x") is None


def test_ready():
    assert classify_page("https://gemini.google.com/app/abcdef0123456789", REPORT) == "ready"


def test_redirect_to_app_is_signed_out():
    assert classify_page("https://gemini.google.com/app?utm_source=x", "<html></html>") == "signed_out"


def test_sign_in_control_is_signed_out():
    assert classify_page("https://gemini.google.com/app/abcdef0123456789", SIGNED_OUT) == "signed_out"


def test_missing_report():
    assert classify_page("https://gemini.google.com/app/abcdef0123456789", "<html><body>chat</body></html>") == "missing_report"
