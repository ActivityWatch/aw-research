import typing
import logging
from typing import List, Dict, Optional, Tuple, Set

import argparse
import re
import json
from urllib.parse import urlparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps

import toml
import pytz
import pydash
import matplotlib.pyplot as plt
import pandas as pd
import joblib

from aw_core.models import Event
from aw_transform import flood, filter_period_intersect, union_no_overlap
from aw_client import ActivityWatchClient

from .plot_sunburst import sunburst


logger = logging.getLogger(__name__)
memory = joblib.Memory("./.cache/joblib")


def _read_class_csv(filename) -> List[Tuple[str, str, Optional[str]]]:
    with open(filename) as f:
        classes = []
        for line in f.readlines():
            if line.strip() and not line.startswith("#"):
                re, cat, parent = (line.strip().split(";") + [""])[:3]
                classes.append((re, cat, parent or None))
        return classes


def test_read_class_csv():
    assert _read_class_csv("categories.example.csv")


def _read_class_toml(filename) -> List[Tuple[str, str, Optional[str]]]:
    classes = []
    with open(filename) as f:
        data = toml.load(f)

    def _register_category_object(d, cat_name=None, parent=None):
        """Recursively registers categories"""
        if isinstance(d, str):
            assert cat_name
            classes.append((d, cat_name, parent))
        elif isinstance(d, dict):
            for k in d:
                if k == "$re":
                    # Handle this case last
                    continue
                _register_category_object(d[k], cat_name=k, parent=cat_name)
            if "$re" in d:
                _register_category_object(d["$re"], cat_name=cat_name, parent=parent)
                d.pop("$re")

    _register_category_object(data["categories"])
    return classes


def test_read_class_toml():
    assert _read_class_toml("categories.example.toml")


classes: Optional[List[Tuple[str, str, Optional[str]]]] = None
parent_categories: Optional[Dict[str, str]] = None


def _init_classes(
    filename: str = None, new_classes: List[Tuple[str, str, Optional[str]]] = None
):
    global classes, parent_categories

    if filename and filename.endswith("csv"):
        classes = _read_class_csv(filename)
    elif filename and filename.endswith("toml"):
        classes = _read_class_toml(filename)
    elif new_classes:
        classes = new_classes
    else:
        raise Exception

    assert classes
    parent_categories = {tag: parent for _, tag, parent in classes if parent}


def requires_init_classes(f):
    @wraps(f)
    def g(*args, **kwargs):
        if parent_categories is None:
            raise Exception("Classes not initialized, run _init_classes first.")
        return f(*args, **kwargs)

    return g


@requires_init_classes
def get_parent_categories(cat: str) -> Set[str]:
    assert parent_categories  # just to quiet typechecker, checked by decorator

    # Recursive
    if cat in parent_categories:
        cats = {parent_categories[cat]}
        for parent in tuple(cats):
            cats |= get_parent_categories(parent)
        return cats
    return set()


hier_sep = "->"


@requires_init_classes
def build_category_hierarchy(cat: str, app: str = None) -> str:
    assert parent_categories  # just to quiet typechecker, checked by decorator

    # Recursive
    s = cat
    if cat in parent_categories:
        parent = parent_categories[cat]
        parents_of_parent = build_category_hierarchy(parent)
        if parents_of_parent:
            s = f"{parents_of_parent} {hier_sep} {s}"
    if app:
        app = app.lstrip("www.").rstrip(".com")
        if app.lower() not in s.lower():
            s = f"{s} {hier_sep} {app}"
    return s


@requires_init_classes
def classify(
    events: List[Event], include_app=False, max_category_depth=3
) -> List[Event]:
    assert classes  # just to quiet typechecker, checked by decorator

    for e in events:
        e.data["$tags"] = set()
        e.data["$category_hierarchy"] = "Uncategorized"

    for re_pattern, cat, _ in classes:
        r = re.compile(re_pattern)
        for e in events:
            for attr in ["title", "app", "url"]:
                if attr not in e.data:
                    continue
                if cat not in e.data["$tags"] and r.findall(e.data[attr]):
                    e.data["$tags"].add(cat)
                    e.data["$tags"] |= get_parent_categories(cat)

    for e in events:
        app = e.data.get("app", None) if include_app else None
        for cat in e.data["$tags"]:
            # Always assign the deepest category
            new_cat_hier = build_category_hierarchy(cat, app=app)
            if "$category_hierarchy" in e.data:
                old_cat_hier = e.data["$category_hierarchy"]
                if old_cat_hier.count(hier_sep) >= new_cat_hier.count(hier_sep):
                    continue
            e.data["$category_hierarchy"] = new_cat_hier

        # Restrict maximum category depth
        e.data["$category_hierarchy"] = _restrict_category_depth(
            e.data["$category_hierarchy"], max_category_depth
        )

    for e in events:
        if not e.data["$tags"]:
            e.data["$tags"].add("Uncategorized")

    return events


def _hostname(url: str) -> str:
    return urlparse(url).netloc


def group_by_url_hostname(events: List[Event]) -> Dict[str, List[Event]]:
    return pydash.group_by(events, lambda e: _hostname(e.data["url"]))


def unfold_hier(s: str) -> List[str]:
    cats = s.split(" -> ")
    cats_s = []
    for i in range(1, len(cats) + 1):
        cats_s.append(" -> ".join(cats[:i]))
    return cats_s


def time_per_category(events: List[Event], unfold=True) -> typing.Counter[str]:
    c: typing.Counter[str] = Counter()
    for e in events:
        if unfold:
            cats = unfold_hier(e.data["$category_hierarchy"])
        else:
            cats = [e.data["$category_hierarchy"]]
        for cat in cats:
            # FIXME: This will be wrong when subcategories with the same name exist with different parents
            c[cat] += e.duration.total_seconds()
    return c


def _plot_category_hierarchy_sunburst(events):
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
        return sorted(
            [
                (k, v["time"], dict_hier_to_list_hier(v["subcats"]))
                for k, v in d.items()
            ],
            key=lambda t: -t[1],
        )

    data = dict_hier_to_list_hier(data)

    sunburst(data, total=sum(t[1] for t in data))
    plt.subplots_adjust(0, 0, 1, 1)


def _restrict_category_depth(s: str, n: int) -> str:
    return " -> ".join(s.split(" -> ")[:n])


def time_per_app(events):
    c = Counter()
    for e in events:
        if "app" in e.data:
            c[e.data["app"]] += e.duration.total_seconds()
    return c


def query2ify(f) -> str:
    """Decorator that transforms a Python function into query2 strings using inspection"""
    import inspect

    srclines = inspect.getsource(f).split("\n")
    # remove decoration and function definition
    srclines = srclines[2:]
    # remove comments (as query2 doesn't yet support them)
    srclines = [ln.split("#")[0] for ln in srclines]
    # remove indentation
    srclines = [ln.strip() for ln in srclines]
    # remove blank lines
    srclines = [ln for ln in srclines if ln]
    # remove import statements
    srclines = [
        ln for ln in srclines if not (ln.startswith("import") or ln.startswith("from"))
    ]
    # replace `return ...` with `RETURN = ...`
    srclines = [
        ln if "return" not in ln else ln.replace("return", "RETURN = ")
        for ln in srclines
    ]
    return ";\n".join(srclines) + ";"


def build_query(hostname: str):
    query = _query_complete
    query = query.replace('hostname = ""', f'hostname = "{hostname}"')
    return query


# The following function is later turned into a query string through introspection.
# Fancy logic will obviously not work either.
# TODO: This doesn't correctly handle web buckets since they don't have a hostname set
# NOTE: fmt: off is used since query2ify assumes single-line statements
# fmt: off
@query2ify
def _query_complete():  # noqa
    from aw_transform import (query_bucket, find_bucket, filter_keyvals, exclude_keyvals, period_union, concat)

    hostname = ""  # set in preprocessing

    browsernames_chrome = ["Chromium"]  # TODO: Include more browsers
    browsernames_ff = ["Firefox"]  # TODO: Include more browsers

    events = flood(query_bucket(find_bucket("aw-watcher-window", hostname)))
    events_afk = query_bucket(find_bucket("aw-watcher-afk", hostname))  # TODO: Readd flooding for afk-events once a release has been made that includes the flooding-fix
    events_web_chrome = flood(query_bucket(find_bucket("aw-watcher-web-chrome")))
    events_web_ff = flood(query_bucket(find_bucket("aw-watcher-web-firefox")))

    # Combine window events with web events
    events_browser_chrome = filter_keyvals(events, "app", browsernames_chrome)
    events_web_chrome = filter_period_intersect(events_web_chrome, events_browser_chrome)

    events_browser_ff = filter_keyvals(events, "app", browsernames_ff)
    events_web_ff = filter_period_intersect(events_web_ff, events_browser_ff)

    events_web = concat(events_web_chrome, events_web_ff)

    # TODO: Browser events should only be excluded when there's a web-event replacing it
    events = exclude_keyvals(events, "app", browsernames_chrome)
    events = exclude_keyvals(events, "app", browsernames_ff)
    events = concat(events, events_web)

    # Filter away all inactive (afk and non-audible) time
    events_notafk = filter_keyvals(events_afk, "status", ["not-afk"])
    events_audible = filter_keyvals(events_web, "audible", [True])
    events_active = period_union(events_notafk, events_audible)
    events = filter_period_intersect(events, events_active)

    return events
# fmt: on


def _get_events_toggl(since: datetime, filepath: str) -> List[Event]:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
        rows = [l.strip().split(",") for l in lines]
        header = rows[0]
        rows = rows[1:]
        entries: List[Dict] = [{"data": dict(zip(header, row))} for row in rows]
        for e in entries:
            for s in ["Start", "End"]:
                yyyy, mm, dd = map(int, e["data"].pop(f"{s} date").split("-"))
                HH, MM, SS = map(int, e["data"].pop(f"{s} time").split(":"))
                e["data"][s] = datetime(yyyy, mm, dd, HH, MM, SS).astimezone(
                    pytz.timezone("Europe/Stockholm")
                )
            e["timestamp"] = e["data"].pop("Start")
            e["duration"] = e["data"].pop("End") - e["timestamp"]
            del e["data"]["User"]
            del e["data"]["Email"]
            del e["data"]["Duration"]

            e["data"]["app"] = e["data"]["Project"]
            e["data"]["title"] = e["data"]["Description"]

    events = [Event(**e) for e in entries]
    events = [e for e in events if since.astimezone(timezone.utc) < e.timestamp]
    return events


def _get_events_smartertime(since: datetime, filepath: str = "auto") -> List[Event]:
    # TODO: Use aw_research.importers.smartertime to generate json file if filepath is smartertime export (.csv)
    if filepath == "auto":
        from glob import glob

        filepath = sorted(glob("data/private/smartertime_export_*.awbucket.json"))[-1]

    print(f"Loading smartertime data from {filepath}")
    with open(filepath) as f:
        data = json.load(f)
        events = [Event(**e) for e in data["events"]]

    # Filter out events before `since`
    events = [e for e in events if since.astimezone(timezone.utc) < e.timestamp]

    # Filter out no-events and non-phone events
    events = [
        e for e in events if any(s in e.data["activity"] for s in ["phone:", "call:"])
    ]

    # Normalize to window-bucket data schema
    for e in events:
        e.data["app"] = e.data["activity"]
        e.data["title"] = e.data["app"]

    return events


@memory.cache(ignore=["awc"])
def get_events(
    awc: ActivityWatchClient,
    hostname: str,
    since: datetime,
    end: datetime,
    include_smartertime="auto",
    include_toggl=None,
) -> List[Event]:
    query = build_query(hostname)
    logger.debug(f"Query:\n{query}")

    result = awc.query(query, timeperiods=[(since, end)])
    events = [Event(**e) for e in result[0]]

    if include_smartertime:
        events = union_no_overlap(
            events, _get_events_smartertime(since, filepath=include_smartertime)
        )
        events = sorted(events, key=lambda e: e.timestamp)

    if include_toggl:
        events = union_no_overlap(
            events, _get_events_toggl(since, filepath=include_toggl)
        )
        events = sorted(events, key=lambda e: e.timestamp)

    # Filter by time
    events = [
        e
        for e in events
        if since.astimezone(timezone.utc) < e.timestamp
        and e.timestamp + e.duration < end.astimezone(timezone.utc)
    ]
    assert all(since.astimezone(timezone.utc) < e.timestamp for e in events)
    assert all(e.timestamp + e.duration < end.astimezone(timezone.utc) for e in events)

    # Filter out events without data (which sometimes happens for whatever reason)
    events = [e for e in events if e.data]

    for event in events:
        if "app" not in event.data:
            if "url" in event.data:
                event.data["app"] = urlparse(event.data["url"]).netloc
            else:
                print("Unexpected event: ", event)

    events = [e for e in events if e.data]
    return events


def test_hostname():
    assert _hostname("http://activitywatch.net/") == "activitywatch.net"
    assert _hostname("https://github.com/") == "github.com"


def _print_category(events, cat="Uncategorized", n=10):
    print(f"Showing top {n} from category: {cat}")
    events = [
        e for e in sorted(events, key=lambda e: -e.duration) if cat in e.data["$tags"]
    ]
    print(f"Total time: {sum((e.duration for e in events), timedelta(0))}")
    groups = {
        k: (v[0].data, sum((e.duration for e in v), timedelta(0)))
        for k, v in pydash.group_by(
            events, lambda e: e.data.get("title", "unknown")
        ).items()
    }
    for _, (v, duration) in list(sorted(groups.items(), key=lambda g: -g[1][1]))[:n]:
        print(str(duration).split(".")[0], f"{v['title'][:60]} [{v['app']}]")


def _datetime_arg(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def _build_argparse(parser):
    parser.add_argument("--start", type=_datetime_arg)
    parser.add_argument("--end", type=_datetime_arg)

    subparsers = parser.add_subparsers(dest="cmd2")
    subparsers.add_parser("summary")
    subparsers.add_parser("summary_plot").add_argument("--save")
    subparsers.add_parser("apps")
    subparsers.add_parser("cat").add_argument("category")

    cat_plot = subparsers.add_parser("cat_plot")
    cat_plot.add_argument("--save")
    cat_plot.add_argument("category", nargs="+")

    return parser


def pprint_secs_hhmmss(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return (
        (f"{int(hours)}h".rjust(4) if hours else "").ljust(5)
        + (f"{int(minutes)}m".rjust(3) if minutes else "").ljust(4)
        + (f"{int(seconds)}s".rjust(3))
    )


def _print_summary(events):
    start = min(e.timestamp for e in events)
    end = max(e.timestamp + e.duration for e in events)
    duration = sum((e.duration for e in events), timedelta(0))
    coverage = duration / (end - start)
    print(f"    Start:  {start}")
    print(f"      End:  {end}")
    print(f"     Span:  {end - start}")
    print(f" Duration:  {duration}")
    print(f" Coverage:  {round(100 * coverage)}%")
    print()


day_offset = timedelta(hours=4)


def _plot_category_daily_trend(events, categories):
    for cat in categories:
        events_cat = [e for e in events if cat in e.data["$category_hierarchy"]]
        ts = pd.Series(
            [e.duration.total_seconds() / 3600 for e in events_cat],
            index=pd.DatetimeIndex([e.timestamp for e in events_cat]).tz_convert("UTC"),
        )
        ts = ts.resample("1D").apply("sum")
        ax = ts.plot(label=cat, legend=True)
        ax = (
            ts.rolling(7, min_periods=2)
            .mean()
            .plot(label=f"{cat} 7d rolling", legend=True)
        )
        ax = (
            ts.rolling(30, min_periods=2)
            .mean()
            .plot(label=f"{cat} 30d rolling", legend=True)
        )
    ax.set_ylabel("Hours")
    plt.xticks(rotation="vertical")
    plt.ylim(0)


def _main(args):
    _init_classes("categories.toml")

    if args.cmd2 in ["summary", "summary_plot", "apps", "cat", "cat_plot"]:
        if not args.end:
            args.end = datetime.now()
        if not args.start:
            how_far_back = timedelta(hours=1 * 12)
            args.start = args.end - how_far_back
        events = get_events(
            args.start,
            args.end,
            include_toggl="./data/private/Toggl_time_entries_2017-12-17_to_2018-11-11.csv",
        )
        _print_summary(events)

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
        elif args.cmd2 == "cat_plot":
            _plot_category_daily_trend(events, args.category)
            if args.save:
                plt.savefig(args.save, bbox_inches="tight")
            else:
                plt.show()
        elif args.cmd2 == "summary_plot":
            _plot_category_hierarchy_sunburst(events)
            if args.save:
                plt.savefig(args.save, bbox_inches="tight")
            else:
                plt.show()
    else:
        print(f"unknown subcommand to classify: {args.cmd2}")


if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="")
    _parser = _build_argparse(_parser)
    _main(_parser.parse_args())
