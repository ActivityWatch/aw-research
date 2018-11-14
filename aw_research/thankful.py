import re
from pprint import pprint
from collections import defaultdict
from typing import List, Dict, Optional
import logging

import aw_client

# pip install google-api-python-client
import apiclient

logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)

re_video_id = re.compile(r"watch\?v=[a-zA-Z0-9\-_]+")
re_patreon_id = re.compile(r"patreon.com/[a-zA-Z0-9\-_]+")
re_bitcoin_addr = re.compile(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}")
re_eth_addr = re.compile(r"0x[A-Fa-f0-9]{40}")
re_email_addr = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_DEVELOPER_KEY = "AIzaSyDSB0CRo8l4cLhxZtOSWEGuAUXfUMUBEV" + "Y"  # slight obfuscation to prevent automated mining
youtube = apiclient.discovery.build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                                    developerKey=YOUTUBE_DEVELOPER_KEY)


class PaymentMethod:
    def __init__(self):
        self.url = None


def find_patreon_link(text: str) -> str:
    # Find Patreon links, they are usually in the Links part of the profile but are sometimes present in user and video descriptions
    # (which is unavailable through the API: https://stackoverflow.com/a/33027866/965332)
    found = re_patreon_id.findall(text)
    if len(found) > 1:
        logger.warning("Found more than one patreon address")
    return found[0] if found else None


def find_bitcoin_address(text: str) -> Optional[str]:
    # https://stackoverflow.com/questions/21683680/regex-to-match-bitcoin-addresses
    found = re_bitcoin_addr.findall(text)
    if len(found) > 1:
        logger.warning("Found more than one bitcoin address")
    return found[0] if found else None


def find_eth_address(text: str) -> Optional[str]:
    found = re_eth_addr.findall(text)
    if len(found) > 1:
        logger.warning("Found more than one ethereum address")
    return found[0] if found else None


def find_email_address(text: str) -> Optional[str]:
    found = re_email_addr.findall(text)
    if len(found) > 1:
        logger.warning("Found more than one email address")
    return found[0] if found else None


assert find_patreon_link("patreon.com/3blue1brown")
assert find_eth_address("0xbD2940e549C38Cc6b201767a0238c2C07820Ef35")
assert find_email_address("erik@bjareho.lt")


class Creator:
    """Creators are currently bound to platforms since cross-platform
       identity is still a non-trivial problem"""
    def __init__(self, service=None, identifier=None):
        self.service = service
        self.id = identifier
        self.title = None
        self.description = None

        # This should be a database query in the future
        self.creations = list()

        self.payment_methods = {}

    def __repr__(self):
        return "<Creator('{}', title='{}', payment_methods='{}')>".format(
            self.id,
            self.title,
            str(list(self.payment_methods.keys()))
        )

    def add_youtube_data(self):
        """This might not belon here when class is made more general"""
        # API Explorer: https://developers.google.com/apis-explorer/#p/youtube/v3/youtube.channels.list
        response = youtube.channels().list(id=self.id, part="snippet").execute()
        if response["items"]:
            creator_data = response["items"][0]
            self.title = creator_data["snippet"]["title"]
            self.description = creator_data["snippet"]["description"]

    def find_payment_methods(self):
        if self.description:
            self._find_patreon(self.description)
            self._find_bitcoin(self.description)
            self._find_eth(self.description)
            self._find_email(self.description)
        else:
            print('No channel description')

        for c in self.creations:
            if "patreon" not in self.payment_methods:
                self._find_patreon(c.description)
            if "bitcoin" not in self.payment_methods:
                self._find_bitcoin(c.description)
            if "eth" not in self.payment_methods:
                self._find_eth(c.description)
            if "email" not in self.payment_methods:
                self._find_email(c.description)

    def register_creation(self, creation: "Content"):
        self.creations.append(creation)

    def _find_patreon(self, text: str):
        patreon_link = find_patreon_link(text)
        if patreon_link:
            self.payment_methods["patreon"] = patreon_link

    def _find_bitcoin(self, text: str):
        bitcoin_addr = find_bitcoin_address(text)
        if bitcoin_addr:
            self.payment_methods["bitcoin"] = bitcoin_addr

    def _find_eth(self, text: str):
        eth_addr = find_eth_address(text)
        if eth_addr:
            self.payment_methods["eth"] = eth_addr

    def _find_email(self, text: str):
        addr = find_email_address(text)
        if addr:
            self.payment_methods["email"] = addr


class Content:
    def __init__(self, identifier=None, title=None):
        self.id = identifier
        self.title = title
        self.description = None

        self.duration = 0

        # Misc data
        self.data = {}

    def __repr__(self):
        return "<Content('{}', title='{}', duration={})>".format(self.id, self.title, self.duration)

    def add_youtube_data(self):
        """This might not belong here when class is made more general"""
        # API Explorer: https://developers.google.com/apis-explorer/#p/youtube/v3/youtube.videos.list
        # Code example: https://github.com/youtube/api-samples/blob/master/python/search.py
        try:
            response = youtube.videos().list(id=self.id, part="snippet").execute()
            if response["items"]:
                video_data = response["items"][0]
                self.id = video_data["id"]
                self.title = video_data["snippet"]["title"]
                self.description = video_data["snippet"]["description"]
                self.data["channelId"] = video_data["snippet"]["channelId"]
        except apiclient.errors.HttpError as e:
            print(e.content)

    @property
    def url(self) -> Optional[str]:
        return "https://youtube.com/watch?v=" + self.id if self.id else None

    @property
    def uri(self):
        """
         Idea for using uri's to identify content. Not sure if a good idea or not. Premature at least.

         On the format: <service>:<type>:<id>
         Examples:
          - spotify:track:5avVpUakfMHD6qGpaH26CF  (this is valid in the Spotify API)
          - youtube:video:dvzpvXLbpv4
        """
        return self.service + ":" + self.type + ":" + self.id


def find_youtube_content(events) -> List[Content]:
    """Finds YouTube content in events"""
    videos = defaultdict(Content)  # type: Dict[str, Content]

    for event in events:
        if "youtube.com/watch?v=" in event.data["url"]:
            found = re_video_id.findall(event.data["url"])
            if found:
                video_id = found[0][8:]
                videos[video_id].duration += event.duration.total_seconds()

    for id_, video in videos.items():
        video.id = id_

    return list(videos.values())


def get_channels_from_videos(videos: List[Content]):
    """Finds channels from a set of videos"""
    channels = defaultdict(lambda: Creator(service="youtube"))  # type: Dict[str, Creator]
    channel_id_set = {video.data["channelId"] for video in videos if "channelId" in video.data}

    for channel_id in channel_id_set:
        channel = channels[channel_id]
        channel.id = channel_id
        channel.add_youtube_data()

    return list(channels.values())


def assign_videos_to_channels(videos, channels):
    channels = {channel.id: channel for channel in channels}

    for video in videos:
        if "channelId" in video.data:
            channel = channels[video.data["channelId"]]
            channel.register_creation(video)


from joblib import Memory
location = './.cache/thankful'
memory = Memory(location, verbose=0)


@memory.cache()
def get_yt_videos():
    awapi = aw_client.ActivityWatchClient("thankful-test", testing=True)
    web_events = awapi.get_events(bucket_id="aw-watcher-web-chrome", limit=-1)

    yt_videos = find_youtube_content(web_events)
    for video in yt_videos:
        video.add_youtube_data()
    return yt_videos


@memory.cache()
def get_channels(yt_videos):
    channels = get_channels_from_videos(yt_videos)
    assign_videos_to_channels(yt_videos, channels)
    for channel in channels:
        channel.find_payment_methods()
    return channels


def _main():
    logging.basicConfig(level=logging.DEBUG)

    channels = get_channels(get_yt_videos())

    # for channel in channels:
    #     if channel.payment_methods:
    #         print(channel)

    for c in channels:
        if c.payment_methods or c.description and re.findall('(BTC|[Bb]itcoin)|(ETH|[Ee]ther(eum)?)', c.description):
            print("-" * 80)
            print(c)
            print(c.description)

    n_with_payment_methods = len(list(filter(lambda c: c.payment_methods, channels)))
    print("Number of found channels with payment methods: {} out of {}".format(n_with_payment_methods, len(channels)))

    for method in ["eth", "bitcoin", "patreon", "email"]:
        n_with_method = len([c for c in channels if method in c.payment_methods])
        print(" - {}: {} out of {}".format(method, n_with_method, len(channels)))

    # pprint(channels)


if __name__ == "__main__":
    _main()
