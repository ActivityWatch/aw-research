from datetime import datetime, timedelta

import pandas as pd

from aw_client import ActivityWatchClient


def get_events(bid):
    return ActivityWatchClient("test", testing=True).get_events(bid, start=datetime.now() - timedelta(days=7), limit=-1)


def to_dataframe(events):
    return pd.DataFrame(dict(timestamp=e.timestamp, duration=e.duration, **e.data) for e in events).set_index('timestamp')


if __name__ == "__main__":
    events = get_events("aw-watcher-window_erb-laptop2-arch")
    df = to_dataframe(events)
    print(df.tail(5))
    print(df.groupby('app').sum().drop('title', axis=1).sort_values('duration', ascending=False))

    print(df.groupby('app', as_index=True).resample('1D').agg({"duration": "sum"}).reset_index().set_index(['timestamp', 'app']).sort_index())
