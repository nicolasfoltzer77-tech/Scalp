#!/usr/bin/env python3
import time
import logging

logging.basicConfig(level=logging.INFO)

def main():
    logging.info("follower.py started")
    while True:
        time.sleep(5)

if __name__ == "__main__":
    main()
