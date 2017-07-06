import os
from typing import List

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
