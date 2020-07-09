from typing import List, Tuple
from datetime import datetime, time, timedelta, timezone

import pandas as pd

from aw_core import Event


def split_event_on_time(event: Event, timestamp: datetime) -> Tuple[Event, Event]:
    event1 = Event(**event)
    event2 = Event(**event)
    assert timestamp > event.timestamp
    event1.duration = timestamp - event1.timestamp
    event2.duration = (event2.timestamp + event2.duration) - timestamp
    event2.timestamp = timestamp
    assert event1.timestamp < event2.timestamp
    assert event.duration == event1.duration + event2.duration
    return event1, event2


def next_hour(timestamp: datetime) -> datetime:
    return datetime.combine(timestamp.date(), time(timestamp.hour)).replace(
        tzinfo=timestamp.tzinfo
    ) + timedelta(hours=1)


def test_next_hour() -> None:
    assert next_hour(datetime(2019, 1, 1, 6, 23)) == datetime(2019, 1, 1, 7)
    assert next_hour(datetime(2019, 1, 1, 23, 23)) == datetime(2019, 1, 2, 0)


def split_event_on_hour(event: Event) -> List[Event]:
    hours_crossed = (event.timestamp + event.duration).hour - event.timestamp.hour
    if hours_crossed == 0:
        return [event]
    else:
        _next_hour = next_hour(event.timestamp)
        event1, event_n = split_event_on_time(event, _next_hour)
        return [event1, *split_event_on_hour(event_n)]


def test_split_event_on_hour() -> None:
    e = Event(
        timestamp=datetime(2019, 1, 1, 11, 30, tzinfo=timezone.utc),
        duration=timedelta(minutes=1),
    )
    assert len(split_event_on_hour(e)) == 1

    e = Event(
        timestamp=datetime(2019, 1, 1, 11, 30, tzinfo=timezone.utc),
        duration=timedelta(hours=2),
    )
    split_events = split_event_on_hour(e)
    assert len(split_events) == 3


def start_of_day(dt: datetime) -> datetime:
    today = dt.date()
    return datetime(today.year, today.month, today.day, tzinfo=timezone.utc)


def end_of_day(dt: datetime) -> datetime:
    return start_of_day(dt) + timedelta(days=1)


def get_week_start(dt: datetime) -> datetime:
    start = dt - timedelta(days=dt.date().weekday())
    return datetime.combine(start.date(), time())


def is_in_same_week(dt1: datetime, dt2: datetime) -> bool:
    return get_week_start(dt1) == get_week_start(dt2)


def split_into_weeks(start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
    if start == end:
        return []
    elif is_in_same_week(start, end):
        return [(start, end)]
    else:
        split = get_week_start(start) + timedelta(days=7)
        return [(start, split)] + split_into_weeks(split, end)


def test_split_into_weeks() -> None:
    split = split_into_weeks(datetime(2019, 1, 3, 12), datetime(2019, 1, 18, 0, 2))
    for dtstart, dtend in split:
        print(dtstart, dtend)
    assert len(split) == 3


def split_into_days(start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
    if start == end:
        return []
    elif start.date() == end.date():
        return [(start, end)]
    else:
        split = datetime.combine(start.date(), time()) + timedelta(days=1)
        return [(start, split)] + split_into_days(split, end)


def test_split_into_days() -> None:
    split = split_into_days(datetime(2019, 1, 3, 12), datetime(2019, 1, 6, 0, 2))
    for dtstart, dtend in split:
        print(dtstart, dtend)
    assert len(split) == 4


def verify_no_overlap(events: List[Event]):
    try:
        assert all(
            [
                e1.timestamp + e1.duration <= e2.timestamp
                for e1, e2 in zip(events[:-1], events[1:])
            ]
        )
    except AssertionError as e:
        n_overlaps = 0
        total_overlap = timedelta()
        for e1, e2 in zip(events[:-1], events[1:]):
            if e1.timestamp + e1.duration > e2.timestamp:
                overlap = (e1.timestamp + e1.duration) - e2.timestamp
                n_overlaps += 1
                total_overlap += overlap
        print(
            f"[WARNING] Found {n_overlaps} events overlapping, totalling: {total_overlap}"
        )


# TODO: Write test that ensures timezone localization is handled correctly
def categorytime_per_day(events, category):
    events = [e for e in events if category in e.data["$category_hierarchy"]]
    if not events:
        raise Exception("No events to calculate on")
    ts = pd.Series(
        [e.duration.total_seconds() / 3600 for e in events],
        index=pd.DatetimeIndex([e.timestamp for e in events]).tz_localize(None),
    )
    return ts.resample("1D").apply("sum")


# TODO: Refactor into categorytime_per_hour? (that you just pass a day of events to)
def categorytime_during_day(
    events: List[Event], category: str, day: datetime
) -> pd.Series:
    events = [e for e in events if category in e.data["$category_hierarchy"]]
    events = [e for e in events if e.timestamp > day]
    _events = []
    for e in events:
        _events.extend(split_event_on_hour(e))
    events = _events
    ts = pd.Series(
        [e.duration.total_seconds() / 3600 for e in events],
        index=pd.DatetimeIndex([e.timestamp for e in events]),
    )
    return ts.resample("1H").apply("sum")
