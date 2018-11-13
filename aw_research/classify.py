from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import argparse
import re

from aw_core.models import Event
from aw_core.timeperiod import TimePeriod
from aw_transform import flood, filter_period_intersect
from aw_client import ActivityWatchClient

import pytz
import pydash

from .plot_sunburst import sunburst


def read_class_csv(filename) -> List[Tuple[str, ...]]:
    with open(filename) as f:
        return [(*line.strip().split(";"), '')[:3] for line in f.readlines() if line.strip() and not line.startswith("#")]


classes = read_class_csv('category_regexes.csv')
parent_categories = {tag: parent for _, tag, parent in classes}


def get_parent_categories(cat: str) -> set:
    # Recursive
    if cat in parent_categories:
        cats = {parent_categories[cat]}
        for parent in tuple(cats):
            cats |= get_parent_categories(parent)
        return cats
    return set()


def build_category_hierarchy(cat: str, app: str = None) -> str:
    # Recursive
    s = cat
    if cat in parent_categories:
        parent = parent_categories[cat]
        parents_of_parent = build_category_hierarchy(parent)
        if parents_of_parent:
            s = parents_of_parent + " -> " + s
    if app:
        app = app.lstrip("www.").rstrip(".com")
        if app.lower() not in s.lower():
            s = s + " -> " + app
    return s


def classify(events, include_app=False):
    for event in events:
        event.data["$tags"] = set()
        event.data["$category_hierarchy"] = "Uncategorized"

    for re_pattern, cat, _ in classes:
        r = re.compile(re_pattern)
        for event in events:
            for attr in ["title", "app", "url"]:
                if attr not in event.data:
                    continue
                if cat not in event.data["$tags"] and \
                   r.findall(event.data[attr]):
                    app = event.data['app'] if include_app and 'app' in event.data else None
                    event.data["$category_hierarchy"] = build_category_hierarchy(cat, app=app)
                    event.data["$tags"].add(cat)
                    event.data["$tags"] |= get_parent_categories(cat)

    for e in events:
        if not e.data["$tags"]:
            e.data["$tags"].add("Uncategorized")

    return events


def _hostname(url):
    return urlparse(url).netloc


def group_by_url_hostname(events):
    return pydash.group_by(events, lambda e: _hostname(e.data["url"]))


def duration_of_groups(groups: Dict[Any, List[Event]]):
    groups_eventdurations = pydash.map_values(
        groups, lambda g: pydash.map_(g, lambda e: e.duration.total_seconds()))  # type: Dict[Any, float]

    return pydash.map_values(
        groups_eventdurations, lambda g: pydash.reduce_(g, lambda total, d: total + d))


def unfold_hier(s: str) -> List[str]:
    cats = s.split(" -> ")
    cats_s = []
    for i in range(1, len(cats) + 1):
        cats_s.append(" -> ".join(cats[:i]))
    return cats_s


def time_per_category(events, unfold=True):
    c = Counter()
    for e in events:
        if unfold:
            cats = unfold_hier(e.data["$category_hierarchy"])
        else:
            cats = [e.data["$category_hierarchy"]]
        for cat in cats:
            c[cat] += e.duration.total_seconds()
    return c


def plot_category_hierarchy_sunburst(events):
    counter = time_per_category(events, unfold=False)
    data = {}
    for cat in counter:
        cat_levels = cat.split(" -> ")
        level = data
        for c in cat_levels:
            if c not in level:
                level[c] = {"time": 0, "subcats": {}}
            level[c]["time"] += counter[cat]
            level = level[c]["subcats"]

    def dict_hier_to_list_hier(d):
        return sorted([(k, v['time'], dict_hier_to_list_hier(v['subcats'])) for k, v in d.items()], key=lambda t: -t[1])
    data = dict_hier_to_list_hier(data)

    sunburst(data, total=sum(t[1] for t in data))
    import matplotlib.pyplot as plt
    plt.subplots_adjust(0, 0, 1, 1)
    plt.show()


def time_per_app(events):
    c = Counter()
    for e in events:
        if "app" in e.data:
            c[e.data["app"]] += e.duration.total_seconds()
    return c


# The following function is later turned into a query string through introspection.
# Fancy logic will obviously not work either.
def query_func():  # noqa
    browsernames = ["Chromium"]  # TODO: Include more browsers
    events = flood(query_bucket(find_bucket("aw-watcher-window")))
    events_web = flood(query_bucket(find_bucket("aw-watcher-web")))
    events_afk = flood(query_bucket(find_bucket("aw-watcher-afk")))

    # Combine window events with web events
    events_browser = filter_keyvals(events, "app", browsernames)
    events_web = filter_period_intersect(events_web, events_browser)
    events = exclude_keyvals(events, "app", browsernames)
    events = concat(events, events_web)

    # Filter away non-afk and non-audible time
    events_notafk = filter_keyvals(events_afk, "status", ["not-afk"])
    events_audible = filter_keyvals(events_web, "audible", [True])
    events_active = period_union(events_notafk, events_audible)
    events = filter_period_intersect(events, events_active)

    RETURN = events


def _get_events_toggl(since) -> List[Event]:
    with open('./data/private/Toggl_time_entries_2017-12-17_to_2018-11-11.csv', 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        rows = [l.strip().split(',') for l in lines]
        header = rows[0]
        rows = rows[1:]
        entries: List[Dict] = [{'data': dict(zip(header, row))} for row in rows]
        for e in entries:
            for s in ['Start', 'End']:
                yyyy, mm, dd = map(int, e['data'].pop(f'{s} date').split("-"))
                HH, MM, SS = map(int, e['data'].pop(f'{s} time').split(':'))
                e['data'][s] = datetime(yyyy, mm, dd, HH, MM, SS).astimezone(pytz.timezone('Europe/Stockholm'))
            e['timestamp'] = e['data'].pop('Start')
            e['duration'] = e['data'].pop('End') - e['timestamp']
            del e['data']['User']
            del e['data']['Email']
            del e['data']['Duration']

            e['data']['app'] = e['data']['Project']
            e['data']['title'] = e['data']['Description']

    events = [Event(**e) for e in entries]
    events = [e for e in events if since.astimezone(timezone.utc) < e.timestamp]
    return events


def _get_events_smartertime(since) -> List[Event]:
    import json
    with open('data/private/smartertime_export_2018-11-10_bf03574a.awbucket.json') as f:
        data = json.load(f)
        events = [Event(**e) for e in data['events']]

    # Filter out events before `since`
    events = [e for e in events if since.astimezone(timezone.utc) < e.timestamp]

    # Filter out no-events and non-phone events
    events = [e for e in events if any(s in e.data['activity'] for s in ['phone:', 'call:'])]

    # Normalize to window-bucket data schema
    for e in events:
        e.data['app'] = e.data['activity']
        e.data['title'] = e.data['app']

    return events


def _split_event(e: Event, dt: datetime) -> Tuple[Event, Optional[Event]]:
    if e.timestamp < dt < e.timestamp + e.duration:
        e1 = deepcopy(e)
        e2 = deepcopy(e)
        e1.duration = dt - e.timestamp
        e2.timestamp = dt
        e2.duration = (e.timestamp + e.duration) - dt
        return (e1, e2)
    else:
        return (e, None)


def test_split_event():
    now = datetime(2018, 1, 1, 0, 0).astimezone(timezone.utc)
    td1h = timedelta(hours=1)
    e = Event(timestamp=now, duration=2 * td1h, data={})
    e1, e2 = _split_event(e, now + td1h)
    assert e1.timestamp == now
    assert e1.duration == td1h
    assert e2.timestamp == now + td1h
    assert e2.duration == td1h


def _union_no_overlap(events1, events2):
    """Merges two eventlists and removes overlap, the first eventlist will have precedence

    Example:
      events1  | xxx    xx     xxx     |
      events1  |  ----     ------   -- |
      result   | xxx--  xx ----xxx  -- |
    """
    # TODO: Move to aw-transform

    events1 = deepcopy(events1)
    events2 = deepcopy(events2)

    # I looked a lot at aw_transform.union when I wrote this
    events_union = []
    e1_i = 0
    e2_i = 0
    while e1_i < len(events1) and e2_i < len(events2):
        e1 = events1[e1_i]
        e2 = events2[e2_i]
        e1_p = TimePeriod(e1.timestamp, e1.timestamp + e1.duration)
        e2_p = TimePeriod(e2.timestamp, e2.timestamp + e2.duration)

        if e1_p.intersects(e2_p):
            if e1.timestamp <= e2.timestamp:
                events_union.append(e1)
                _, e2_next = _split_event(e2, e1.timestamp + e1.duration)
                if e2_next:
                    events2[e2_i] = e2_next
                else:
                    e2_i += 1
                e1_i += 1
            else:
                e2_next, e2_next2 = _split_event(e2, e1.timestamp)
                events_union.append(e2_next)
                e2_i += 1
                if e2_next2:
                    events2.insert(e2_i, e2_next2)
        else:
            if e1.timestamp < e2.timestamp:
                events_union.append(e1)
                e1_i += 1
            else:
                events_union.append(e2)
                e2_i += 1
    events_union += events1[e1_i:]
    events_union += events2[e2_i:]
    return events_union


def test_union_no_overlap():
    from pprint import pprint

    now = datetime(2018, 1, 1, 0, 0)
    td1h = timedelta(hours=1)
    events1 = [Event(timestamp=now + 2 * i * td1h, duration=td1h, data={'test': 1}) for i in range(3)]
    events2 = [Event(timestamp=now + (2 * i + 0.5) * td1h, duration=td1h, data={'test': 2}) for i in range(3)]

    events_union = _union_no_overlap(events1, events2)
    # pprint(events_union)
    dur = sum((e.duration for e in events_union), timedelta(0))
    assert dur == timedelta(hours=4, minutes=30)

    events_union = _union_no_overlap(events2, events1)
    # pprint(events_union)
    dur = sum((e.duration for e in events_union), timedelta(0))
    assert dur == timedelta(hours=4, minutes=30)

    events1 = [Event(timestamp=now + (2 * i) * td1h, duration=td1h, data={'test': 1}) for i in range(3)]
    events2 = [Event(timestamp=now, duration=5 * td1h, data={'test': 2})]
    events_union = _union_no_overlap(events1, events2)
    pprint(events_union)
    dur = sum((e.duration for e in events_union), timedelta(0))
    assert dur == timedelta(hours=5, minutes=0)


def get_events(since, include_smartertime=True, include_toggl=True) -> List[Event]:
    awc = ActivityWatchClient("test", testing=True)

    import inspect
    sourcelines = inspect.getsource(query_func).split("\n")
    sourcelines = sourcelines[1:]  # remove function definition
    sourcelines = [l.split("#")[0] for l in sourcelines]  # remove comments (as query2 doesn't yet support them)
    sourcelines = [l.strip() for l in sourcelines]  # remove indentation
    sourcelines = [l for l in sourcelines if l]  # remove blank lines
    query = ";\n".join(sourcelines)

    result = awc.query(query, start=since, end=datetime.now())
    events = [Event(**e) for e in result[0]]

    if include_smartertime:
        events = _union_no_overlap(events, _get_events_smartertime(since))
        events = sorted(events, key=lambda e: e.timestamp)

    if include_toggl:
        events = _union_no_overlap(events, _get_events_toggl(since))
        events = sorted(events, key=lambda e: e.timestamp)

    # Filter out events without data (which sometimes happens for whatever reason)
    events = [e for e in events if e.data]

    for event in events:
        if 'app' not in event.data:
            if 'url' in event.data:
                event.data['app'] = urlparse(event.data['url']).netloc
            else:
                print('Unexpected event: ', event)

    events = [e for e in events if e.data]
    return events


def test_hostname():
    assert _hostname("http://activitywatch.net/") == "activitywatch.net"
    assert _hostname("https://github.com/") == "github.com"


def _print_category(events, cat="Uncategorized", n=10):
    print(f"Showing top {n} from category: {cat}")
    events = [e for e in sorted(events, key=lambda e: -e.duration) if cat in e.data["$tags"]]
    print(f"Total time: {sum((e.duration for e in events), timedelta(0))}")
    groups = {k: (v[0].data, sum((e.duration for e in v), timedelta(0))) for k, v in pydash.group_by(events, lambda e: e.data.get('title', "unknown")).items()}
    for _, (v, duration) in list(sorted(groups.items(), key=lambda g: -g[1][1]))[:n]:
        print(str(duration).split(".")[0], f"{v['title'][:60]} [{v['app']}]")


def _build_argparse(parser):
    subparsers = parser.add_subparsers(dest='cmd2')
    subparsers.add_parser('summary')
    subparsers.add_parser('summary_plot')
    subparsers.add_parser('apps')
    subparsers.add_parser('cat').add_argument('category')
    return parser


def pprint_secs_hhmmss(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return ((f"{int(hours)}h".rjust(4) if hours else '').ljust(5) +
            (f"{int(minutes)}m".rjust(3) if minutes else '').ljust(4) +
            (f"{int(seconds)}s".rjust(3)))


def _main(args):
    if args.cmd2 in ["summary", "summary_plot", "apps", "cat"]:
        how_far_back = timedelta(hours=1 * 12)
        events = get_events(datetime.now() - how_far_back)
        start = min(e.timestamp for e in events)
        end = max(e.timestamp + e.duration for e in events)
        duration = sum((e.duration for e in events), timedelta(0))
        coverage = duration / (end - start)
        print(f"    Start:  {start}")
        print(f"      End:  {end}")
        print(f"     Span:  {end-start}")
        print(f" Duration:  {duration}")
        print(f" Coverage:  {round(100 * coverage)}%")
        print()

        events = classify(events, include_app=False)
        # pprint([e.data["$tags"] for e in classify(events)])
        if args.cmd2 in ["summary", "apps"]:
            print(f"Total time: {sum((e.duration for e in events), timedelta(0))}")
            if args.cmd2 == "summary":
                time_per = time_per_category(events)
            elif args.cmd2 == "apps":
                time_per = time_per_app(events)
            for c, s in time_per.most_common():
                print(pprint_secs_hhmmss(s) + f"    {c}")
        elif args.cmd2 == "cat":
            _print_category(events, args.category, 30)
        elif args.cmd2 == "summary_plot":
            plot_category_hierarchy_sunburst(events)
    else:
        print(f'unknown subcommand to classify: {args.cmd2}')


if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description='')
    _parser = _build_argparse(_parser)
    _main(_parser.parse_args())
