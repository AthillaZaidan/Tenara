import argparse
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import portable


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, content=b"content"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def archive(self, *, changed=None, extra=None, missing=None):
        files = {
            f"{portable.SNAPSHOT}/database.dump": b"dump",
            f"{portable.SNAPSHOT}/runtime.json": b"{}",
            "docker-compose.yml": b"services: {}",
            "scripts/portable.py": b"# tool",
            "web/package-lock.json": b"{}",
            "web/app/layout.tsx": b"// layout",
            "services/api/uv.lock": b"lock",
            "services/api/app/main.py": b"# app",
            "services/api/app/models/__init__.py": b"# models",
            "services/api/storage/owner/image": b"image",
        }
        manifest = {
            "format": portable.FORMAT,
            "database": {"files": [{"key": "owner/image", "size": 5}],
                         "tables": {}, "migrations": ["0014"]},
            "files": {},
        }
        import hashlib
        for name, data in files.items():
            manifest["files"][name] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        files[portable.MANIFEST] = json.dumps(manifest).encode()
        if changed:
            files.update(changed)
        if missing:
            del files[missing]
        if extra:
            files.update(extra)
        path = self.root / "snapshot.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return path

    def test_source_collects_new_assets_and_code_but_not_credentials_or_caches(self):
        wanted = ["web/public/assets/music.mp3", "web/public/fonts/font.woff2",
                  "web/lib/story.ts", "services/api/app/main.py", "scripts/portable.py",
                  "services/api/app/models/file.py",
                  ".env.example"]
        excluded = [".env", "services/api/.env", "web/.env.local", "web/node_modules/a.js",
                    "services/api/.venv/x", "web/.next/build.js", "web/tsconfig.tsbuildinfo",
                    "services/api/storage/image", "services/api/models/weights.npz",
                    "docs/research/private.md", ".playwright-mcp/screen.png", "web/AGENTS.md"]
        for name in wanted + excluded:
            self.file(name)
        actual = {p.relative_to(self.root).as_posix() for p in portable.source_files(self.root)}
        self.assertEqual(actual, set(wanted))

    def test_round_trip_verifies_files_and_refuses_changed_tree(self):
        archive = self.archive()
        destination = self.root / "copy"
        portable.unpack(argparse.Namespace(archive=archive, destination=destination))
        portable.verify_tree(destination)
        (destination / "services/api/storage/owner/image").write_bytes(b"wrong")
        with self.assertRaisesRegex(portable.SnapshotError, "Missing/changed"):
            portable.verify_tree(destination)

    def test_changed_archive_is_rejected_before_extracting(self):
        archive = self.archive(changed={"services/api/storage/owner/image": b"wrong"})
        destination = self.root / "copy"
        with self.assertRaisesRegex(portable.SnapshotError, "Checksum"):
            portable.unpack(argparse.Namespace(archive=archive, destination=destination))
        self.assertFalse(destination.exists())

    def test_missing_uploaded_file_is_rejected(self):
        archive = self.archive(missing="services/api/storage/owner/image")
        with self.assertRaisesRegex(portable.SnapshotError, "contents"):
            portable.verify_archive(archive)

    def test_extra_file_and_path_traversal_are_rejected(self):
        for name in ["extra.txt", "../escaped", "/absolute", "a/../../escaped", "C:/file"]:
            with self.subTest(name=name):
                archive = self.archive(extra={name: b"unexpected"})
                with self.assertRaises(portable.SnapshotError):
                    portable.verify_archive(archive)

    def test_symlinks_and_duplicates_are_rejected(self):
        for link in [True, False]:
            archive = self.root / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("link")
                if link:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "../elsewhere"
                    tar.addfile(info)
                else:
                    tar.addfile(info, io.BytesIO(b""))
                    tar.addfile(info, io.BytesIO(b""))
            with self.assertRaisesRegex(portable.SnapshotError, "Invalid/duplicate"):
                portable.verify_archive(archive)

    def test_unpack_will_not_overwrite_existing_project(self):
        archive = self.archive()
        destination = self.root / "copy"
        destination.mkdir()
        (destination / "user-work").write_text("keep")
        with self.assertRaisesRegex(portable.SnapshotError, "new or empty"):
            portable.unpack(argparse.Namespace(archive=archive, destination=destination))
        self.assertEqual((destination / "user-work").read_text(), "keep")

    def test_file_references_must_have_matching_payload_sizes(self):
        manifest = portable.verify_archive(self.archive())
        manifest["database"]["files"][0]["size"] = 999
        with self.assertRaisesRegex(portable.SnapshotError, "database file"):
            portable.validate_manifest(manifest)

    def test_database_restore_refuses_populated_destination_without_pg_restore(self):
        db = object.__new__(portable.Database)
        db.name = "existing"
        with patch.object(db, "sql", side_effect=["1", "3"]), patch.object(db, "command") as command:
            with self.assertRaisesRegex(portable.SnapshotError, "not empty"):
                db.restore(self.root / "absent.dump")
            command.assert_not_called()

    def test_database_comparison_checks_contents_not_only_counts(self):
        manifest = {"database": {"tables": {"users": {"rows": 1, "digest": "original"}},
                                  "migrations": ["0014"], "files": []}}
        db = object.__new__(portable.Database)
        actual = {**manifest["database"], "tables": {"users": {"rows": 1, "digest": "changed"}}}
        with (
            patch.object(db, "sql", return_value=json.dumps(actual)),
            patch.object(db, "metadata_sql", return_value="SELECT 1;"),
            self.assertRaisesRegex(portable.SnapshotError, "differs.*tables"),
        ):
            portable.verify_database(db, manifest)


if __name__ == "__main__":
    unittest.main()
