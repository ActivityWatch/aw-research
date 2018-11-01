from typing import List, Dict, Any, Set
from urllib.parse import urlparse
from collections import Counter
from datetime import datetime, timedelta
import argparse
import re

from aw_core.models import Event
from aw_transform import flood
from aw_client import ActivityWatchClient

import pydash


def read_csv_mapping(filename) -> Dict[str, str]:
    with open(filename) as f:
        lines = [tuple(line.strip().split(";")[:2]) for line in f.readlines() if line.strip() and not line.startswith("#")]
        return dict(lines)


classes = read_csv_mapping('category_regexes.csv')
parent_categories = read_csv_mapping('parent_categories.csv')


def get_parent_categories(cat: str) -> set:
    # Recursive
    if cat in parent_categories:
        cats = {parent_categories[cat]}
        for parent in tuple(cats):
            cats |= get_parent_categories(parent)
        return cats
    return set()


def classify(events):
    for event in events:
        event.data["categories"] = set()

    for re_pattern, cat in classes.items():
        r = re.compile(re_pattern)
        for event in events:
            for attr in ["title", "app"]:
                if attr not in event.data:
                    continue
                if cat not in event.data["categories"] and \
                   r.findall(event.data[attr]):
                    event.data["categories"].add(cat)
                    event.data["categories"] |= get_parent_categories(cat)

    for e in events:
        if not e.data["categories"]:
            e.data["categories"].add("Uncategorized")

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


def time_per_category(events):
    c = Counter()
    for e in events:
        cats = e.data["categories"]
        for cat in cats:
            c[cat] += e.duration.total_seconds()
    return c


def time_per_category_with_flooding(events):
    cats = {cat for e in events for cat in e.data["categories"]}
    c = Counter()
    for cat in cats:
        events_with_cat = [e for e in events if cat in e.data["categories"]]
        events_with_cat_flooded = flood(events_with_cat, pulsetime=60)
        c[cat] += sum(e.duration.total_seconds() for e in events_with_cat_flooded)
    return c


# The following function is later turned into a query string through introspection.
# Fancy logic will obviously not work either.
# TODO: Combine browser events with
def query_func():  # noqa
    browsernames = ["Chromium"]  # TODO: Include more browsers
    events = flood(query_bucket(find_bucket("aw-watcher-window")))
    events_afk = flood(query_bucket(find_bucket("aw-watcher-afk")))
    events = filter_period_intersect(events, filter_keyvals(events_afk, "status", ["not-afk"]))

    events_web = flood(query_bucket(find_bucket("aw-watcher-web")))
    events_browser = filter_keyvals(events, "app", browsernames)
    events_web = filter_period_intersect(events_web, events_browser)
    events = exclude_keyvals(events, "app", browsernames)

    RETURN = [events, events_web]


def get_events() -> List[Event]:
    awc = ActivityWatchClient("test", testing=True)

    import inspect
    sourcelines = inspect.getsource(query_func).split("\n")
    sourcelines = sourcelines[1:]  # remove function definition
    sourcelines = [l.split("#")[0] for l in sourcelines]  # remove comments (as query2 doesn't yet support them)
    sourcelines = [l.strip() for l in sourcelines]  # remove indentation
    sourcelines = [l for l in sourcelines if l]  # remove blank lines
    query = ";\n".join(sourcelines)
    print(query)

    result = awc.query(query, start=datetime.now() - timedelta(days=3), end=datetime.now())
    events = [Event(**e) for e in result[0][0] + result[0][1]]
    return events


def test_hostname():
    assert _hostname("http://activitywatch.net/") == "activitywatch.net"
    assert _hostname("https://github.com/") == "github.com"


def _print_category(events, cat="Uncategorized", n=10):
    print(f"Showing top {n} from category: {cat}")
    events = [e for e in sorted(events, key=lambda e: -e.duration) if cat in e.data["categories"]]
    print(f"Total time: {sum((e.duration for e in events), timedelta(0))}")
    groups = {k: sum((e.duration for e in v), timedelta(0)) for k, v in pydash.group_by(events, lambda e: e.data['title']).items()}
    for k, v in list(sorted(groups.items(), key=lambda g: -g[1]))[:n]:
        print(v, k)


def _build_argparse(parser):
    subparsers = parser.add_subparsers(dest='cmd2')
    summary = subparsers.add_parser('summary')
    category = subparsers.add_parser('cat')
    category.add_argument('category')
    return parser


def _main(args):
    # events = get_events("aw-watcher-web-chrome")
    # groups = group_by_url_hostname(events)
    # duration_pairs = pydash.to_pairs(duration_of_groups(groups))
    # pprint(sorted(duration_pairs, key=lambda p: p[1]))

    if args.cmd2 in ["summary", 'cat']:
        # TODO: Use a query and filter AFK
        events = get_events()
        print(min(e.timestamp for e in events), max(e.timestamp + e.duration for e in events))
        events = classify(events)
        # pprint([e.data["categories"] for e in classify(events)])
        if args.cmd2 == "summary":
            print(f"Total time: {sum((e.duration for e in events), timedelta(0))}")
            time_per_cat = time_per_category_with_flooding(events)
            for c, s in time_per_cat.most_common():
                hours, remainder = divmod(s, 3600)
                minutes, seconds = divmod(remainder, 60)
                print((f"{int(hours)}h".rjust(4) if hours else '').ljust(5) +
                      (f"{int(minutes)}m".rjust(3) if minutes else '').ljust(4) +
                      (f"{int(seconds)}s".rjust(3) + f"    {c}"))
        elif args.cmd2 == "cat":
            _print_category(events, args.category, 30)
    else:
        print(f'unknown subcommand to classify: {args.cmd2}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    parser = _build_argparse(parser)
    args = parser.parse_args()
    _main(args)
