from aw_core.models import Event

from aw_research.redact import redact_words


def test_redact_word():
    e = Event(data={"label": "Sensitive stuff", "desc": "Lorem ipsum..."})
    e = redact_words([e], "(Sensitive stuff)")[0]
    assert "sensitive" not in e.data["label"]
    assert "REDACTED" in e.data["label"]
    assert "REDACTED" in e.data["desc"]

    e = redact_words([e], "(sensitive)", ignore_case=True)[0]
    assert "sensitive" not in e.data["label"]
