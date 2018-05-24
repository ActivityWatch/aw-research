from random import randint, random
from datetime import datetime, timezone, timedelta
from typing import List

import matplotlib.pyplot as plt
from matplotlib.dates import date2num

now = datetime.now(tz=timezone.utc)
now = datetime(year=2017, month=7, day=7)


def color_gen():
    i = 0
    colors = ["r", "y", "g"]
    while True:
        yield colors[i % 3]
        i += 1


def barchart(x: List[datetime], bar_sets: List[List[float]]):
    """
    Based on:

     - https://stackoverflow.com/questions/17827748/matplotilb-bar-chart-diagonal-tick-labels
     - https://matplotlib.org/examples/pylab_examples/bar_stacked.html
     -
    """
    plt.figure()

    x = date2num(x)

    ax = plt.subplot(111)
    ax.set_xlabel("time")
    ax.set_ylabel("duration")
    ax.xaxis_date()
    # ax.set_xticklabels(["{}:{:02d}".format(dt.hour, dt.minute) for dt in x], rotation=45)

    n = len(bar_sets[0])
    bottom = [0] * n
    colors = color_gen()
    for bars in bar_sets:
        color = next(colors)
        ax.bar(x, bars, width=1 / 24 / 1.5, align="center", color=color, bottom=bottom, label="a")
        bottom = [bottom[i] + bars[i] for i in range(n)]

    ax.legend()
    plt.show()

if __name__ == "__main__":
    plt.style.use('ggplot')

    n = 50
    x = [now + timedelta(hours=i) for i in range(n)]
    y1 = [random() * 15 for i in range(n)]
    y2 = [random() * (30 - y1[i]) for i in range(n)]
    y3 = [random() * (60 - y1[i] - y2[i]) for i in range(n)]

    barchart(x, [y1, y2, y3])
