from __future__ import annotations
from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass
class Segment:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

def make_segments(index: pd.DatetimeIndex, train_days: int, test_days: int, segments: int) -> List[Segment]:
    if index.tz is None: index = index.tz_localize("UTC")
    start = index.min(); end = index.max()
    segs: List[Segment] = []
    cur_train_start = start
    for _ in range(segments):
        train_end = cur_train_start + pd.Timedelta(days=train_days)
        test_end = train_end + pd.Timedelta(days=test_days)
        if test_end > end: break
        segs.append(Segment(cur_train_start, train_end, train_end, test_end))
        cur_train_start = cur_train_start + pd.Timedelta(days=test_days)
    return segs