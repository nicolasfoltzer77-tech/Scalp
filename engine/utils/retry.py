#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import time
from typing import Callable, Any, Type, Iterable

def retry(fn: Callable[..., Any],
          tries: int = 3,
          delay: float = 1.0,
          backoff: float = 1.5,
          exceptions: Iterable[Type[BaseException]] = (Exception,),
          on_retry: Callable[[int, BaseException], None] | None = None,
          *args, **kwargs) -> Any:
    att = 0
    cur_delay = delay
    while True:
        try:
            return fn(*args, **kwargs)
        except exceptions as e:
            att += 1
            if att >= tries:
                raise
            if on_retry:
                on_retry(att, e)
            time.sleep(cur_delay)
            cur_delay *= backoff