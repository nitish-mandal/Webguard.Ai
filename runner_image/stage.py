"""Trusted idle staging process. Never read, import or execute uploaded source."""

import signal
import time


def expired(signum, frame):
    raise SystemExit(0)


signal.signal(signal.SIGALRM, expired)
signal.alarm(60)
while True:
    time.sleep(1)
