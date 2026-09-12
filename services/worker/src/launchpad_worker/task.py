"""One Fargate task processes exactly one already-persisted job."""

import sys
import os
import threading

from launchpad_api.store import store

from .runner import process


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m launchpad_worker.task JOB_ID ATTEMPT")
    job = store.claim_by_id(sys.argv[1], int(sys.argv[2]))
    if not job:
        return
    watchdog = threading.Timer(1800, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    try:
        process(job, fixture=job.get("planner_mode") == "fixture")
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
