#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fsm_ready(fr):
    """
    FOLLOWER invariant :
    - autorise action uniquement si req_step == done_step
    """
    return int(fr["req_step"] or 0) == int(fr["done_step"] or 0)

