from datetime import datetime, timedelta, timezone

from aw_core import Event

from aw_research.util import categorytime_per_day


def _event(cat_hierarchy: str, hours: float = 1.0) -> Event:
    return Event(
        timestamp=datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc),
        duration=timedelta(hours=hours),
        data={"$category_hierarchy": cat_hierarchy},
    )


def test_categorytime_per_day_matches_segment_not_substring():
    # "P" is a leaf under Media; it must NOT match "Programming".
    events = [_event("Work -> Programming"), _event("Media -> P")]
    assert categorytime_per_day(events, "P").sum() == 1.0
    assert categorytime_per_day(events, "Programming").sum() == 1.0


def test_categorytime_per_day_includes_subcategories():
    # A parent category counts time spent in its subcategories.
    events = [_event("Work -> Programming"), _event("Work -> Email")]
    assert categorytime_per_day(events, "Work").sum() == 2.0


def test_categorytime_per_day_no_prefix_substring_match():
    # "Work" must not match "Homework" via substring.
    events = [_event("Homework")]
    try:
        categorytime_per_day(events, "Work")
    except Exception:
        pass  # no matching events -> raises, which is the correct behavior here
    else:
        raise AssertionError("'Work' should not match 'Homework'")
