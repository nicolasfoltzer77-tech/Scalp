#!/usr/bin/env python3
from enum import Enum, auto

class State(Enum):
    IDLE = auto()
    FOLLOW = auto()
    GEST = auto()
    OPEN = auto()
    CLOSE = auto()

class FSM:
    def __init__(self):
        self.state = State.IDLE

    def on_tick(self, ctx=None):
        if self.state == State.IDLE:
            self.state = State.FOLLOW
        elif self.state == State.FOLLOW:
            self.state = State.GEST
        elif self.state == State.GEST:
            self.state = State.OPEN
        elif self.state == State.OPEN:
            self.state = State.CLOSE
        elif self.state == State.CLOSE:
            self.state = State.IDLE
        return self.state
