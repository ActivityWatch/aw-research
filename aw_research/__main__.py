import logging
import argparse
import sys
from pprint import pprint
from collections import defaultdict
from datetime import timedelta

from aw_transform import heartbeat_reduce
from aw_transform.flood import flood
from aw_transform.simplify import simplify_string

from aw_client import ActivityWatchClient

from aw_research.redact import redact_words
from aw_research.algorithmia import run_sentiment, run_LDA
from aw_research.merge import merge_close_and_similar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def assert_no_overlap(events):
    overlap = False
    events = sorted(events, key=lambda e: e.timestamp)
    for e1, e2 in zip(events[:-1], events[1:]):
        e1_end = e1.timestamp + e1.duration
        gap = e2.timestamp - e1_end
        if gap < timedelta(0):
            logger.warning("Events overlapped: {}".format(gap))
            overlap = True
    assert not overlap


def _get_window_events(n=1000):
    client = ActivityWatchClient("aw-analyser", testing=True)
    buckets = client.get_buckets()

    bucket_id = None
    for _bid in buckets.keys():
        if "window" in _bid and "testing" not in _bid:
            bucket_id = _bid

    if bucket_id:
        return client.get_events(bucket_id, limit=n)
    else:
        print("Did not find bucket")
        return []


def _load_sensitive_words():
    with open("sensitive_words.txt") as f:
        return (word.lower() for word in f.read().split("\n") if word)


def _main_redact():
    logger.info("Retrieving events...")
    events = _get_window_events()

    logger.info("Redacting...")
    sensitive_words = list(_load_sensitive_words())
    logger.info("Sensitive words: " + str(sensitive_words))
    events = redact_words(events, sensitive_words)


def _main_analyse():
    logger.info("Retrieving events...")
    events = _get_window_events()

    logger.info("Running analysis...")
    titles = list({e.data["title"] for e in events})
    out = run_LDA(titles)
    pprint(out.result)

    out = run_sentiment(titles)
    pprint([r for r in out.result if r["sentiment"] != 0])

    out = run_sentiment(" ".join(titles))
    pprint([r for r in out.result if r["sentiment"] != 0])


def _main_merge():
    logger.info("Retrieving events...")
    events = _get_window_events(n=1000)
    events = simplify_string(events)

    merged_events = merge_close_and_similar(events)
    print("{} events became {} after merging of similar ones".format(len(events), len(merged_events)))

    # Debugging
    assert_no_overlap(events)
    assert_no_overlap(merged_events)
    print_most_common_titles(events)
    print_most_common_titles(merged_events)


def _main_heartbeat_reduce():
    logger.info("Retrieving events...")
    events = _get_window_events()
    events = simplify_string(events)

    logger.info("Beating hearts together...")
    merged_events = heartbeat_reduce(events, pulsetime=10)

    # Debugging
    assert_no_overlap(events)
    assert_no_overlap(merged_events)
    print_most_common_titles(events)
    print_most_common_titles(merged_events)


def _main_flood():
    logger.info("Retrieving events...")
    events = _get_window_events()
    events = simplify_string(events)

    logger.info("Flooding...")
    merged_events = flood(events)

    # Debugging
    assert_no_overlap(events)
    assert_no_overlap(merged_events)
    print_most_common_titles(events)
    print_most_common_titles(merged_events)


def print_most_common_titles(events):
    counter = defaultdict(lambda: timedelta(0))
    for e in events:
        counter[e.data["title"]] += e.duration

    print("-" * 30)

    def total_duration(events):
        return sum((e.duration for e in events), timedelta(0))
    print("Total duration: {}".format(total_duration(events)))

    pairs = sorted(zip(counter.values(), counter.keys()), reverse=True)
    for duration, title in pairs[:15]:
        print("{:15s} - {}".format(str(duration), title))

    print("-" * 30)


if __name__ == "__main__":
    args = list(sys.argv)
    args.pop(0)
    if len(args) > 0:
        action = args.pop(0)
    else:
        raise Exception("You need to specify an action")

    if action == "redact":
        _main_redact()
    elif action == "analyse":
        _main_analyse()
    elif action == "merge":
        _main_merge()
    elif action == "flood":
        _main_flood()
    elif action == "heartbeat":
        _main_heartbeat_reduce()
    else:
        print("Invalid action {}".format(action))
