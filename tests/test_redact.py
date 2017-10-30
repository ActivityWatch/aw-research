from aw_core.models import Event

from aw_analysis.redact import redact_words


def test_redact_word():
    e = Event(data={"label": "sensitive", "desc": "Lorem ipsum..."})
    e = redact_words([e], ["sensitive"])[0]
    assert "sensitive" not in e.data["label"]
    assert "REDACTED" in e.data["label"]
    assert "REDACTED" in e.data["desc"]
