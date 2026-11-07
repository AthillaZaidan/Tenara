"""Job worker. Run with:  uv run python worker.py

Later sub-projects import their handler modules here so they register themselves.
"""
import signal
import time
from collections.abc import Callable

from app.db.base import SessionLocal
from app.services.commerce import expire_holds
from app.services.jobs import process_one


def main(poll_interval: float = 1.0, should_stop: Callable[[], bool] = lambda: False) -> None:
    while not should_stop():
        with SessionLocal() as session:
            expire_holds(session)  # release payment holds whose window has passed
            session.commit()
            worked = process_one(session)
        if not worked:
            time.sleep(poll_interval)


if __name__ == "__main__":
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    main(should_stop=lambda: stop["flag"])
