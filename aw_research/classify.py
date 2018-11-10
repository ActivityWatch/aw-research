from typing import List, Dict, Any, Set, Optional, Tuple
from urllib.parse import urlparse
from collections import Counter
from datetime import datetime, timedelta
import argparse
import re

from aw_core.models import Event
from aw_transform import flood
from aw_client import ActivityWatchClient

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


def _get_events_smartertime(since) -> List[Event]:
    import json
    with open('data/private/smartertime_export_2018-11-10_bf03574a.awbucket.json') as f:
        data = json.load(f)
        events = [Event(**e) for e in data['events']]

    # Filter out events before `since`
    from datetime import timezone
    events = [e for e in events if since.astimezone(timezone.utc) < e.timestamp]

    # Filter out no-events and non-phone events
    events = [e for e in events if any(s in e.data['activity'] for s in ['phone:', 'call:'])]

    # Normalize to window-bucket data schema
    for e in events:
        e.data['app'] = e.data['activity']
        e.data['title'] = e.data['app']

    return events


def get_events(since, include_smartertime=False) -> List[Event]:
    awc = ActivityWatchClient("test", testing=True)

    import inspect
    sourcelines = inspect.getsource(query_func).split("\n")
    sourcelines = sourcelines[1:]  # remove function definition
    sourcelines = [l.split("#")[0] for l in sourcelines]  # remove comments (as query2 doesn't yet support them)
    sourcelines = [l.strip() for l in sourcelines]  # remove indentation
    sourcelines = [l for l in sourcelines if l]  # remove blank lines
    query = ";\n".join(sourcelines)
    # print(query)

    result = awc.query(query, start=since, end=datetime.now())
    events = [Event(**e) for e in result[0]]

    if include_smartertime:
        events += _get_events_smartertime(since)
        events = sorted(events, key=lambda e: e.timestamp)

    # Filter out events without data (which sometimes happens for whatever reason)
    events = [e for e in events if e.data]

    from urllib.parse import urlparse
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
    for k, (v, duration) in list(sorted(groups.items(), key=lambda g: -g[1][1]))[:n]:
        print(str(duration).split(".")[0], f"{v['title'][:60]} [{v['app']}]")


def _build_argparse(parser):
    subparsers = parser.add_subparsers(dest='cmd2')
    summary = subparsers.add_parser('summary')
    summary_plot = subparsers.add_parser('summary_plot')
    apps = subparsers.add_parser('apps')
    category = subparsers.add_parser('cat')
    category.add_argument('category')
    return parser


def pprint_secs_hhmmss(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return ((f"{int(hours)}h".rjust(4) if hours else '').ljust(5) +
            (f"{int(minutes)}m".rjust(3) if minutes else '').ljust(4) +
            (f"{int(seconds)}s".rjust(3)))


def _main(args):
    # events = get_events("aw-watcher-web-chrome")
    # groups = group_by_url_hostname(events)
    # duration_pairs = pydash.to_pairs(duration_of_groups(groups))
    # pprint(sorted(duration_pairs, key=lambda p: p[1]))

    if args.cmd2 in ["summary", "summary_plot", "apps", "cat"]:
        how_far_back = timedelta(hours=1 * 24)
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

        events = classify(events)
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
    parser = argparse.ArgumentParser(description='')
    parser = _build_argparse(parser)
    _main(parser.parse_args())
