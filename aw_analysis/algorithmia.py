import os
import logging
from typing import List

import Algorithmia

logger = logging.getLogger(__name__)

if "ALGORITHMIA_API_KEY" in os.environ:
    API_KEY = os.environ["ALGORITHMIA_API_KEY"]
else:
    logger.warn("Env variable ALGORITHMIA_API_KEY not set, Algorithmia will be unavailable.")


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
