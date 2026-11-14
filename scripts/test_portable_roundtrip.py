"""Opt-in integration test: restore the real snapshot into a disposable database.

TENARA_TEST_SNAPSHOT=backups/tenara-lengkap.tar.gz \
TENARA_TEST_API_PYTHON=services/api/.venv/bin/python \
python3 -m unittest discover -s scripts -p 'test_portable_roundtrip.py'
"""

import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

import portable


@unittest.skipUnless(os.environ.get("TENARA_TEST_SNAPSHOT"), "Set TENARA_TEST_SNAPSHOT for round trip")
class SnapshotRoundTrip(unittest.TestCase):
    def test_restored_database_and_uploads_serve_the_same_application(self):
        archive = Path(os.environ["TENARA_TEST_SNAPSHOT"]).resolve()
        python = Path(os.environ.get("TENARA_TEST_API_PYTHON",
                                     "services/api/.venv/bin/python")).absolute()
        project = os.environ.get("TENARA_TEST_COMPOSE_PROJECT", portable.ROOT.name)
        database = "tenara_snapshot_test_" + uuid.uuid4().hex[:12]
        db = portable.Database(database, project)
        with tempfile.TemporaryDirectory(prefix="tenara-roundtrip-") as tmp:
            destination = Path(tmp) / "tenara"
            command = ["python3", str(portable.ROOT / "scripts/portable.py")]
            subprocess.run(command + ["unpack", str(archive), "--destination", str(destination)],
                           check=True)
            command = ["python3", str(destination / "scripts/portable.py"),
                       "--compose-project", project]
            try:
                subprocess.run(command + ["restore", "--database", database],
                               cwd=destination, check=True)
                subprocess.run(command + ["verify", "--database", database],
                               cwd=destination, check=True)
                # Exercise the COPIED backend with the copied uploads and restored DB.
                smoke = """
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db.base import SessionLocal
from app.models import File, GalleryEntry, User
from app.core.security import create_access_token
with TestClient(app) as client, SessionLocal() as session:
    assert client.get('/api/v1/health').status_code == 200
    response = client.get('/api/v1/gallery')
    assert response.status_code == 200
    assert response.json()['data']['items']
    entries = session.scalars(select(GalleryEntry).where(GalleryEntry.status == 'published')).all()
    for entry in entries:
        for suffix in ['', '/passport', '/listings', '/variants']:
            response = client.get('/api/v1/gallery/' + entry.slug + suffix)
            assert response.status_code == 200, (entry.slug, suffix, response.text)
    users = session.scalars(select(User)).all()
    for user in users:
        headers = {'Authorization': 'Bearer ' + create_access_token(user.id)}
        assert client.get('/api/v1/auth/me', headers=headers).status_code == 200
    files = session.scalars(select(File).where(File.deleted_at.is_(None), File.visibility == 'public')).all()
    for file in files:
        response = client.get('/api/v1/files/' + str(file.id))
        assert response.status_code == 200, str(file.id)
        assert len(response.content) == file.size_bytes
    print(f'Restored API smoke passed: {len(entries)} published entries, {len(users)} accounts, {len(files)} public uploads')
"""
                subprocess.run([str(python), "-c", smoke], cwd=destination / "services/api",
                               env={**os.environ, "DATABASE_URL":
                                    f"postgresql+psycopg://tenara:tenara@localhost:5432/{database}",
                                    "STORAGE_DIR": str(destination / "services/api/storage")},
                               check=True)
                # A second restore must refuse to overwrite the populated database.
                again = subprocess.run(command + ["restore", "--database", database],
                                       cwd=destination, capture_output=True, text=True, check=False)
                self.assertNotEqual(again.returncode, 0)
                self.assertIn("not empty", again.stderr)
            finally:
                db.command("dropdb", "-U", db.user, "--if-exists", "--", database)


if __name__ == "__main__":
    unittest.main()
