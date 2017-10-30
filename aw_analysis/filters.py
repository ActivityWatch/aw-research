import logging
from typing import List
from copy import deepcopy

from aw_core.timeperiod import TimePeriod
from aw_core.models import Event
from aw_client import ActivityWatchClient


logger = logging.getLogger(__name__)


def filter_keyvals(events, key, vals, exclude=False) -> List[Event]:
    def p(e):
        # The xor here is a bit tricky, but works nicely
        return exclude ^ any(map(lambda v: e[key] == v, vals))

    return list(filter(p, events))


def filter_short(events, threshold: float = 1):
    # TODO: Try to fill hole in timeline where events have been removed
    #       (if events before and after where are the same)
    #       Useful for filtering AFK data and to make data look "smoother".
    #       Might be something for another function
    return [e for e in events if e.duration.total_seconds() > threshold]


def filter_datafields(events: List[Event], fields: List[str]):
    """Filters away specific datafield from every event in a list"""
    for e in events:
        for field in fields:
            if field in e.data:
                e.data.pop(field)
    return events


def _get_event_period(event: Event) -> TimePeriod:
    # TODO: Better parsing of event duration
    start = event.timestamp
    end = start + event.duration
    return TimePeriod(start, end)


def _replace_event_period(event: Event, period: TimePeriod) -> Event:
    e = deepcopy(event)
    e.timestamp = period.start
    e.duration = period.duration
    return e


def filter_period_intersect(events: List[Event], filterevents: List[Event]) -> List[Event]:
    """
    Filters away all events or time periods of events in which a
    filterevent does not have an intersecting time period.

    Useful for example when you want to filter away events or
    part of events during which a user was AFK.

    Example:
      windowevents_notafk = filter_period_intersect(windowevents, notafkevents)
    """

    events = sorted(events, key=lambda e: e.timestamp)
    filterevents = sorted(filterevents, key=lambda e: e.timestamp)
    filtered_events = []

    e_i = 0
    f_i = 0
    while e_i < len(events) and f_i < len(filterevents):
        event = events[e_i]
        filterevent = filterevents[f_i]
        ep = _get_event_period(event)
        fp = _get_event_period(filterevent)

        ip = ep.intersection(fp)
        if ip:
            # If events itersected, add event with intersected duration and try next event
            filtered_events.append(_replace_event_period(event, ip))
            e_i += 1
        else:
            # No intersection, check if event is before/after filterevent
            if ep.end <= fp.start:
                # Event ended before filter event started
                e_i += 1
            elif fp.end <= ep.start:
                # Event started after filter event ended
                f_i += 1
            else:
                logger.warning("Unclear if/how this could be reachable, skipping period")
                e_i += 1
                f_i += 1

    return filtered_events


def test_filter_data():
    awapi = ActivityWatchClient("cleaner", testing=True)
    events = awapi.get_events("aw-watcher-web-test", limit=-1)
    events = filter_datafields(events, "title")
    assert "title" not in events[0].data


def test_filter_short():
    # TODO: This was used in dev and does not work.
    awapi = ActivityWatchClient("cleaner", testing=True)
    events = awapi.get_events("aw-watcher-web-test", limit=-1)
    filter_short(events, threshold=1)

    events = awapi.get_events("aw-watcher-window-testing_erb-main2-arch", limit=-1)
    filter_short(events, threshold=1)

    events = awapi.get_events("aw-watcher-afk-testing_erb-main2-arch", limit=-1)
    filter_short(events, threshold=30)


if __name__ == "__main__":
    test_filter_data()
    test_filter_short()
