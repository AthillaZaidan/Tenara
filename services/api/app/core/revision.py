from app.core.errors import StaleRevision


def check_revision(expected: int, current: int) -> None:
    """Optimistic concurrency: reject writes made against an outdated revision."""
    if expected != current:
        raise StaleRevision(f"Expected revision {expected} but current revision is {current}")
