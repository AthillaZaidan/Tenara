"""Job worker. Run with:  uv run python worker.py

Later sub-projects import their handler modules here so they register themselves.
"""
import signal
import time
from collections.abc import Callable

import app.workers.handlers  # noqa: F401  (registers the AI job handlers)
from app.db.base import SessionLocal
from app.services import photos
from app.services.commerce import expire_holds
from app.services.jobs import process_one
from app.services.storage import get_storage


def main(poll_interval: float = 1.0, should_stop: Callable[[], bool] = lambda: False) -> None:
    while not should_stop():
        with SessionLocal() as session:
            expire_holds(session)  # release payment holds whose window has passed
            photos.purge_expired(session, get_storage())  # raw body photos past retention
            session.commit()
            worked = process_one(session)
        if not worked:
            time.sleep(poll_interval)


if __name__ == "__main__":
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    main(should_stop=lambda: stop["flag"])
