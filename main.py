import re
import os
from typing import List
from pprint import pprint

from aw_core.models import Event
from aw_client import ActivityWatchClient

import Algorithmia

API_KEY = os.environ["ALGORITHMIA_API_KEY"]


def run_sentiment(docs: List[str]):
    payload = [{
        "document": doc
    } for doc in docs]
    client = Algorithmia.client(API_KEY)
    algo = client.algo('nlp/SentimentAnalysis/1.0.3')
    return algo.pipe(payload)


def run_LDA(docs: List[str]):
    payload = {
        "docsList": docs,
        "mode": "quality",
        "stopWordsList": ["/"],
    }
    client = Algorithmia.client(API_KEY)
    algo = client.algo('nlp/LDA/1.0.0')
    return algo.pipe(payload)


def get_window_titles(events: List[Event]):
    return [e.data["title"] for e in events]


def _redact_full(event):
    for key in event.data:
        event.data[key] = "redacted"
    return event


def _redact(events, f):
    n = 0
    for i, event in enumerate(events):
        for key in event.data:
            if f(event.data[key]):
                n += 1
                print("Redacting: \"{}\"".format(event.data[key]))
                events[i] = _redact_full(event)
                break
    return events, n


def redact_words(events, words):
    sensitive_words_pattern = "(" + "|".join((re.escape(bw) for bw in sensitive_words)) + ")"
    r = re.compile(sensitive_words_pattern)
    events, n_redacted = _redact(events, lambda s: r.search(s.lower()))
    print("Total: {}\nRedacted: {}\nPercent: {}%".format(len(events), n_redacted, 100 * n_redacted / len(events)))
    return events


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
    events = get_window_events()

    sensitive_words = load_sensitive_words()
    print(sensitive_words)
    events = redact_words(events, sensitive_words)

    # titles = list(set(get_window_titles(events)))
    # docs = titles
    # out = run_LDA(docs)
    # pprint(out.result)

    # titles_doc = " ".join(titles)
    # out = run_sentiment(titles)
    # pprint([r for r in out.result if r["sentiment"] != 0])
