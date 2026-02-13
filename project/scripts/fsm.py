#!/usr/bin/env python3
from enum import Enum

class State(Enum):
    IDLE = "IDLE"
    FOLLOW = "FOLLOW"
    GEST = "GEST"
    OPEN = "OPEN"
    CLOSE = "CLOSE"

class FSM:
    def __init__(self):
        self.state = State.IDLE

    def transition(self, event: str):
        if self.state == State.IDLE and event == "tick":
            self.state = State.FOLLOW
        elif self.state == State.FOLLOW and event == "signal":
            self.state = State.GEST
        elif self.state == State.GEST and event == "open":
            self.state = State.OPEN
        elif self.state == State.OPEN and event == "close":
            self.state = State.CLOSE
        elif self.state == State.CLOSE:
            self.state = State.IDLE
        return self.state
