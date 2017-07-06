from typing import List
from pprint import pprint
import logging

from aw_core.models import Event
from aw_client import ActivityWatchClient

logging.basicConfig(level=logging.INFO)

from .redact import redact_words
from .algorithmia import *

logger = logging.getLogger(__name__)


def get_window_titles(events: List[Event]):
    return [e.data["title"] for e in events]


def get_window_events():
    client = ActivityWatchClient("aw-analyser", testing=True)
    buckets = client.get_buckets()

    bucket_id = None
    for b in buckets:
        if "window" in b:
            bucket_id = b

    if bucket_id:
        return client.get_events(bucket_id, limit=500)
    else:
        print("Did not find bucket")
        return []


def load_sensitive_words():
    with open("sensitive_words.txt") as f:
        return (word for word in f.read().split("\n") if word)


if __name__ == "__main__":
    logger.info("Running analysis...")

    events = get_window_events()

    sensitive_words = list(load_sensitive_words())
    logger.info("Sensitive words: " + str(sensitive_words))
    events = redact_words(events, sensitive_words)

    # titles = list(set(get_window_titles(events)))
    # docs = titles
    # out = run_LDA(docs)
    # pprint(out.result)

    # titles_doc = " ".join(titles)
    # out = run_sentiment(titles)
    # pprint([r for r in out.result if r["sentiment"] != 0])
