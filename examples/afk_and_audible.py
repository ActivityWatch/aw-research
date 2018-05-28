from aw_client import ActivityWatchClient

from aw_research.classify import bucket_query
from aw_transform import filter_period_intersect


def _check_nonoverlapping(events):
    events = sorted(events, key=lambda e: e.timestamp)
    last_end = None
    for e in events:
        end = e.timestamp + e.duration
        if last_end:
            assert last_end <= end
        last_end = end


def merge(events1, events2):
    result = ...
    _check_nonoverlapping(result)
    return result


def all_active_webactivity():
    """Returns activity during non-afk events or when tab is audible"""
    awapi = ActivityWatchClient("test", testing=True)

    bid = bucket_query(awapi, bucket_type="current_webpage")
    tabevents = awapi.get_events(bid, limit=-1)

    bid = bucket_query(awapi, bucket_type="afkstatus")
    afkevents = awapi.get_events(bid, limit=-1)

    afkevents_notafk = list(filter(lambda e: e.data["status"] == "not-afk", afkevents))
    tabevents_audible = list(filter(lambda e: "audible" in e.data and e.data["audible"], tabevents))

    # TODO: Implement merge
    # activeevents = merge(afkevents_notafk, tabevents_audible)
    # This isn't perfect, buggy when a notafk/audible events is contained by another
    activeevents = afkevents_notafk + tabevents_audible

    return filter_period_intersect(tabevents, activeevents)


if __name__ == "__main__":
    from pprint import pprint

    pprint(all_active_webactivity())
