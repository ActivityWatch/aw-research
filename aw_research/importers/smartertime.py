# Code originally from now deprecated repo: https://github.com/ActivityWatch/aw-importer-smartertime

import csv
from datetime import datetime, timedelta, timezone
import secrets
import json

from tabulate import tabulate

from aw_core.models import Event
import aw_client


def parse(filepath):
    events = []
    with open(filepath, 'r') as f:
        c = csv.DictReader(f)
        for r in c:
            # print(r)
            dt = datetime.fromtimestamp(float(r['Timestamp UTC ms']) / 1000)
            tz_h, tz_m = map(int, r['Time'].split("GMT+")[1].split()[0].split(":"))
            dt = dt.replace(tzinfo=timezone(timedelta(hours=tz_h, minutes=tz_m)))
            td = timedelta(milliseconds=float(r['Duration ms']))
            e = Event(timestamp=dt, duration=td, data={
                'activity': r['Activity'],
                'device': r['Device'],
                'place': r['Place'],
                'room': r['Room'],
            })
            events.append(e)
    return events


def import_as_bucket(filepath):
    events = parse(filepath)
    end = max(e.timestamp + e.duration for e in events)
    bucket = {
        'id': f'smartertime_export_{end.date()}_{secrets.token_hex(4)}',
        'created': datetime.now(),
        'event_type': 'smartertime.v0',
        'client': '',
        'hostname': '',
        'data': {
            'readonly': True,
        },
        'events': events,
    }
    return bucket


def print_info(bucket):
    events = bucket['events']
    rows = []
    for a in ['Messenger', 'Plex', 'YouTube', 'Firefox', 'reddit', 'call:', 'Anki', 'Duolingo', 'HelloChinese', 'Notes', 'Gmail', 'Sheets', 'Docs', 'Spotify']:
        rows.append([a, sum((e.duration for e in events if a in e.data['activity']), timedelta(0))])
    rows = sorted(rows, key=lambda r: -r[1])
    print(tabulate(rows, ['title', 'time']))


def default(o):
    if hasattr(o, 'isoformat'):
        return o.isoformat()
    elif hasattr(o, 'total_seconds'):
        return o.total_seconds()
    else:
        raise NotImplementedError


def save_bucket(bucket):
    filename = bucket['id'] + ".awbucket.json"
    with open(filename, 'w') as f:
        json.dump(bucket, f, indent=True, default=default)
    print(f"Saved as {filename}")


def import_to_awserver(bucket):
    awc = aw_client.ActivityWatchClient('smartertime2activitywatch', testing=True)
    buckets = json.loads(json.dumps({"buckets": [bucket]}, default=default))
    awc._post('import', buckets)


if __name__ == '__main__':
    import sys
    assert len(sys.argv) > 1
    filename = sys.argv.pop()
    bucket = import_as_bucket(filename)
    save_bucket(bucket)
    # import_to_awserver(bucket)
    print_info(bucket)
