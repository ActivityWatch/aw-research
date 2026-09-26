from datetime import datetime, timedelta, timezone

from typing import List, Optional, Tuple

import pytest
from aw_core import Event

from aw_research import classify as cl
from aw_research.util import (
    categorytime_during_day,
    categorytime_per_day,
    event_categories,
    in_category,
)

CLASSES = [
    ("^$", "Work", None),
    ("Programming", "Programming", "Work"),
    ("ActivityWatch", "ActivityWatch", "Programming"),
    ("aw-server-rust", "Server", "ActivityWatch"),
    ("aw-server-rust.*db", "Datastore", "Server"),
    ("Steam", "Games", None),
    ("Secret", "P", None),
    ("SecretGame", "Games(P)", "P"),
    ("Planning", "Planning", None),
]

T0 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def _event(title: str, hours: float = 1.0, offset_h: float = 0, app="app") -> Event:
    return Event(
        timestamp=T0 + timedelta(hours=offset_h),
        duration=timedelta(hours=hours),
        data={"title": title, "app": app},
    )


@pytest.fixture(autouse=True)
def restore_classes(monkeypatch):
    # restore the module-level classifier config after each test
    for attr in ["classes", "parent_categories"]:
        monkeypatch.setattr(cl, attr, getattr(cl, attr))


@pytest.fixture
def events():
    cl._init_classes(new_classes=CLASSES)
    return cl.classify(
        [
            _event("Programming ActivityWatch", 1, 0),
            _event("Steam", 2, 1),
            _event("SecretGame", 4, 3),
            _event("Planning", 8, 7),
            _event("aw-server-rust db", 16, 15),
        ]
    )


def _hours(events, cat) -> float:
    return categorytime_per_day(events, cat).sum()


def test_category_path(events):
    assert event_categories(events[0]) == ["Work", "Programming", "ActivityWatch"]
    assert event_categories(events[2]) == ["P", "Games(P)"]


def test_top_level_category_assigned(events):
    # A match on a top-level category alone must not leave the event "Uncategorized"
    assert events[1].data["$category_hierarchy"] == "Games"
    assert event_categories(events[1]) == ["Games"]


def test_substring_names_do_not_match(events):
    # "P" must not match "Planning" or "Programming", only itself and its children
    assert _hours(events, "P") == 4
    # "Games" must not match "Games(P)"
    assert _hours(events, "Games") == 2
    assert _hours(events, "Games(P)") == 4
    assert _hours(events, "Planning") == 8


def test_deep_hierarchy(events):
    # Datastore is 5 levels deep
    e = events[4]
    path = ["Work", "Programming", "ActivityWatch", "Server", "Datastore"]
    assert event_categories(e) == path
    # $category_hierarchy is truncated to max_category_depth, $category_path is not
    assert e.data["$category_hierarchy"] == "Work -> Programming -> ActivityWatch"
    assert _hours(events, "Work") == 1 + 16
    assert _hours(events, "Programming") == 1 + 16
    assert _hours(events, "ActivityWatch") == 1 + 16
    assert _hours(events, "Server") == 16
    assert _hours(events, "Datastore") == 16


def test_app_segment_not_a_category():
    cl._init_classes(new_classes=CLASSES)
    (e,) = cl.classify([_event("Steam", app="Lutris")], include_app=True)
    assert e.data["$category_hierarchy"] == "Games -> Lutris"
    assert in_category(e, "Games")
    assert not in_category(e, "Lutris")


def test_fallback_without_category_path():
    e = Event(
        timestamp=T0,
        duration=timedelta(hours=1),
        data={"$category_hierarchy": "Work -> Programming -> ActivityWatch"},
    )
    assert in_category(e, "Programming")
    assert in_category(e, "Work")
    assert not in_category(e, "P")
    assert not in_category(e, "Activity")


def test_categorytime_during_day(events):
    ts = categorytime_during_day(events, "P", T0 - timedelta(hours=1))
    assert ts.sum() == 4
    # empty category matches all events
    ts = categorytime_during_day(events, "", T0 - timedelta(hours=1))
    assert ts.sum() == 1 + 2 + 4 + 8 + 16


def test_tie_broken_by_definition_order():
    classes: List[Tuple[str, str, Optional[str]]] = [("b", "B", None), ("a", "A", None)]
    cl._init_classes(new_classes=classes)
    (e,) = cl.classify([_event("a b")])
    assert e.data["$category_hierarchy"] == "B"
