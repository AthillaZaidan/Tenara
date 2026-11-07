import pytest

from app.services.storage import LocalDiskStorage


def test_put_open_delete(tmp_path):
    s = LocalDiskStorage(tmp_path)
    s.put("a/b.bin", b"hello", "application/octet-stream")
    assert s.open("a/b.bin") == b"hello"
    s.delete("a/b.bin")
    with pytest.raises(FileNotFoundError):
        s.open("a/b.bin")


def test_delete_missing_is_noop(tmp_path):
    LocalDiskStorage(tmp_path).delete("nope")


@pytest.mark.parametrize("key", ["../evil", "a/../../evil", "/etc/passwd"])
def test_path_traversal_rejected(tmp_path, key):
    with pytest.raises(ValueError):
        LocalDiskStorage(tmp_path).put(key, b"x", "text/plain")
