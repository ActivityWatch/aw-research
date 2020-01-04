import os
import logging
from typing import List

try:
    import Algorithmia
except ImportError:
    pass

logger = logging.getLogger(__name__)

API_KEY = os.environ["ALGORITHMIA_API_KEY"] if "ALGORITHMIA_API_KEY" in os.environ else None


def _assert_api_key():
    if API_KEY is None:
        raise Exception("Env variable ALGORITHMIA_API_KEY not set, can't use Algorithmia.")


def run_sentiment(docs: List[str]):
    _assert_api_key()
    payload = [{
        "document": doc
    } for doc in docs]
    client = Algorithmia.client(API_KEY)
    algo = client.algo('nlp/SentimentAnalysis/1.0.3')
    return algo.pipe(payload)


def run_LDA(docs: List[str]):
    _assert_api_key()
    payload = {
        "docsList": docs,
        "mode": "quality",
        "stopWordsList": ["/"],
    }
    client = Algorithmia.client(API_KEY)
    algo = client.algo('nlp/LDA/1.0.0')
    return algo.pipe(payload)
