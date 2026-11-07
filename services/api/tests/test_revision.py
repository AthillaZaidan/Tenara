import pytest

from app.core.errors import StaleRevision
from app.core.revision import check_revision


def test_matching_revision_passes():
    check_revision(3, 3)


def test_stale_revision_raises():
    with pytest.raises(StaleRevision) as exc:
        check_revision(3, 4)
    assert "3" in exc.value.message and "4" in exc.value.message
