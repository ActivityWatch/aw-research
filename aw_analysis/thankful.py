import re
from pprint import pprint
from collections import defaultdict
from typing import List, Dict, Optional

import aw_client

# pip install google-api-python-client
import apiclient

re_video_id = re.compile(r"watch\?v=[a-zA-Z0-9\-_]+")

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_DEVELOPER_KEY = "AIzaSyCUnQRiX0axfETg6YrbppATN2nuNJ2zdw" + str(8)  # slight obfuscation to prevent automated mining
youtube = apiclient.discovery.build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                                    developerKey=YOUTUBE_DEVELOPER_KEY)


class Creator:
    """Creators are currently bound to platforms since cross-platform
       identity is still a non-trivial problem"""
    def __init__(self, service=None, id=None):
        pass

    def __repr__(self):
        return "<Creator('{}', title='{}')>".format(self.id, self.title)

    def add_youtube_data(self):
        """This might not belon here when class is made more general"""
        # API Explorer: https://developers.google.com/apis-explorer/#p/youtube/v3/youtube.channels.list
        response = youtube.channels().list(id=self.id, part="snippet").execute()
        if response["items"]:
            self.id = response["items"][0]["id"]
            self.title = response["items"][0]["snippet"]["title"]


class Content:
    def __init__(self, id=None, title=None):
        self.id = id
        self.title = title

        self.duration = 0

        # Misc data
        self.data = {}

    def __repr__(self):
        return "<Content('{}', title='{}', duration={})>".format(self.id, self.title, self.duration)

    def add_youtube_data(self):
        """This might not belon here when class is made more general"""
        # API Explorer: https://developers.google.com/apis-explorer/#p/youtube/v3/youtube.videos.list
        # Code example: https://github.com/youtube/api-samples/blob/master/python/search.py
        response = youtube.videos().list(id=self.id, part="snippet").execute()
        if response["items"]:
            video_data = response["items"][0]
            self.id = video_data["id"]
            self.title = video_data["snippet"]["title"]
            self.data["channelId"] = video_data["snippet"]["channelId"]

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
    videos = defaultdict(lambda: Content())

    for event in events:
        if "youtube.com/watch?v=" in event.data["url"]:
            # print("Found youtube event: ", event)
            found = re_video_id.findall(event.data["url"])
            if found:
                video_id = found[0][8:]
                videos[video_id].duration += event.duration.total_seconds()

    for id, video in videos.items():
        video.id = id

    return list(videos.values())


def get_channels_from_videos(videos: List[Content]):
    """Finds channels from a set of videos"""
    channels = defaultdict(lambda: Creator())
    channel_id_set = {video.data["channelId"] for video in videos}

    for channel_id in channel_id_set:
        channel = channels[channel_id]
        channel.id = channel_id
        channel.add_youtube_data()

    return list(channels.values())


if __name__ == "__main__":
    awapi = aw_client.ActivityWatchClient("thankful-test", testing=True)
    web_events = awapi.get_events(bucket_id="aw-watcher-web-test", limit=-1)

    yt_videos = find_youtube_content(web_events)
    for video in yt_videos:
        video.add_youtube_data()
    pprint(yt_videos)

    channels = get_channels_from_videos(yt_videos)
    pprint(channels)
