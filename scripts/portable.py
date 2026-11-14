"""Move the current Tenara application, PostgreSQL database, and assets together.

Python 3.12+ and Docker Compose are sufficient. Run --help for commands.
Database commands use the db service in this project's docker-compose.yml.
"""

import argparse
import contextlib
import hashlib
import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ".tenara-snapshot"
MANIFEST = f"{SNAPSHOT}/manifest.json"
FORMAT = 1
SOURCE_ROOTS = ("web", "services/api", "scripts")
SOURCE_FILES = (".gitignore", ".env.example", "docker-compose.yml", "README.md",
                "docs/HANDOFF.md", "docs/PORTABLE.md")
EXCLUDED = {".git", ".venv", "node_modules", ".next", "__pycache__", ".pytest_cache",
            ".ruff_cache", ".vercel", "backups", SNAPSHOT,
            ".taste-skill", "results", "coverage"}
# Only application settings, never source credentials or source machine URLs.
RUNTIME_KEYS = {
    "EMBEDDER", "EMBEDDING_MODEL", "PHOTO_EMBEDDER", "PHOTO_EMBEDDING_MODEL",
    "SEARCH_MIN_SIMILARITY", "PROMPT_INTERPRETER", "LLM_PROVIDER", "LLM_MODEL",
    "HOLD_MINUTES", "DEFAULT_COMMISSION_BPS", "BUYER_SERVICE_FEE_IDR",
    "PHOTO_DEFAULT_RETENTION_MINUTES", "PHOTO_MAX_RETENTION_DAYS", "PHOTO_MAX_BYTES",
    "VLM_TIMEOUT_SECONDS", "UPLOAD_MAX_BYTES", "CLAIM_WINDOW_DAYS",
    "PARTNER_RESPONSE_SLA_HOURS", "FILE_URL_TTL_SECONDS", "ACCESS_TOKEN_HOURS",
}


class SnapshotError(Exception):
    pass


def run(args, *, root=ROOT, **kwargs):
    return subprocess.run(args, cwd=root, check=True, **kwargs)


def environment(root=ROOT):
    """Read ordinary one-line dotenv values; real environment variables win."""
    values = {}
    env_file = root / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip().removeprefix("export ")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() not in RUNTIME_KEYS | {"STORAGE_DIR", "DATABASE_URL"}:
                continue
            parts = shlex.split(value, comments=True)
            values[key.strip()] = " ".join(parts)
    return {**values, **os.environ}


def storage_root(value=None, root=ROOT):
    path = Path(value or environment(root).get("STORAGE_DIR") or "storage")
    return path.resolve() if path.is_absolute() else (root / "services/api" / path).resolve()


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or path.as_posix() != name):
        raise SnapshotError(f"Unsafe snapshot path: {name!r}")
    return path


def source_files(root=ROOT):
    """Package the working tree, including new application files, without local caches."""
    result = [root / name for name in SOURCE_FILES if (root / name).is_file()]
    for folder in SOURCE_ROOTS:
        base = root / folder
        if not base.exists():
            continue
        for current, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and
                             not (Path(current) == root / "services/api" and
                                  d in {"storage", "models"}))
            for name in dirs:
                if (Path(current) / name).is_symlink():
                    raise SnapshotError(f"Symlink directory cannot be packaged: {Path(current) / name}")
            for name in sorted(files):
                path = Path(current) / name
                if ((name.startswith(".env") and name != ".env.example")
                        or name.endswith((".pyc", ".tsbuildinfo", ".log"))
                        or name in {".DS_Store", "next-env.d.ts"}
                        or (path.parent == root / "web" and path.suffix == ".md")):
                    continue
                result.append(path)
    return sorted(set(result))


class Database:
    def __init__(self, database=None, project=None, root=ROOT):
        self.root = root
        self.compose = ["docker", "compose"]
        if project:
            self.compose += ["--project-name", project]
        self.base = self.compose + ["exec", "-T", "db"]
        self.user = self.command("printenv", "POSTGRES_USER").strip()
        self.name = database or self.command("printenv", "POSTGRES_DB").strip()

    def command(self, *args, **kwargs):
        return run(self.base + list(args), root=self.root, capture_output=True,
                   text=True, **kwargs).stdout

    def psql_args(self, database=None):
        return self.base + ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
                            "-U", self.user, "-d", database or self.name]

    def sql(self, sql, database=None):
        return run(self.psql_args(database), root=self.root, input=sql, text=True,
                   capture_output=True).stdout.strip()

    def major(self):
        return int(self.sql("SHOW server_version_num;", "postgres")) // 10000

    def table_names(self):
        return json.loads(self.sql("""
            SELECT coalesce(json_agg(tablename ORDER BY tablename), '[]')
            FROM pg_tables WHERE schemaname = 'public';
        """))

    def metadata_sql(self, *, snapshot=False):
        tables = []
        for name in self.table_names():
            quoted = '"' + name.replace('"', '""') + '"'
            literal = "'" + name.replace("'", "''") + "'"
            tables.append(f"""SELECT {literal} AS name, json_build_object(
                'rows', count(*), 'digest', md5(coalesce(string_agg(
                md5(to_jsonb(t)::text), '' ORDER BY md5(to_jsonb(t)::text)), '')))
                AS value FROM public.{quoted} t""")
        if not tables:
            raise SnapshotError(f"Database {self.name!r} has no application tables")
        return f"""SET TIME ZONE 'UTC';
            SELECT json_build_object(
              'snapshot', {"pg_export_snapshot()" if snapshot else "null"},
              'tables', (SELECT json_object_agg(name, value) FROM (
                {' UNION ALL '.join(tables)}) counts),
              'migrations', (SELECT json_agg(version_num ORDER BY version_num)
                             FROM alembic_version),
              'files', (SELECT coalesce(json_agg(json_build_object(
                'key', storage_key, 'size', size_bytes) ORDER BY storage_key), '[]')
                FROM files WHERE deleted_at IS NULL));
        """

    @contextlib.contextmanager
    def snapshot(self):
        # Keep one transaction alive so metadata and pg_dump read the SAME database snapshot.
        query = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n" + self.metadata_sql(snapshot=True)
        with tempfile.TemporaryFile(mode="w+") as errors:
            proc = subprocess.Popen(self.psql_args(), cwd=self.root, text=True,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
            try:
                proc.stdin.write(query + "\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
                if not line:
                    errors.seek(0)
                    raise SnapshotError("Cannot open database snapshot: " + errors.read())
                yield json.loads(line)
                proc.stdin.write("ROLLBACK;\n\\q\n")
                proc.stdin.flush()
                if proc.wait(timeout=30) != 0:
                    raise SnapshotError("Database snapshot session failed")
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=30)
                proc.stdin.close()
                proc.stdout.close()

    def dump(self, target, snapshot):
        with target.open("wb") as stream:
            run(self.base + ["pg_dump", "-U", self.user, "-d", self.name,
                             "--format=custom", "--no-owner", "--no-privileges",
                             f"--snapshot={snapshot}"], root=self.root, stdout=stream)

    def restore(self, source):
        # Never overwrite a populated database, including one outside the public schema.
        literal = "'" + self.name.replace("'", "''") + "'"
        exists = self.sql(f"SELECT 1 FROM pg_database WHERE datname = {literal};", "postgres")
        if not exists:
            self.command("createdb", "-U", self.user, "--template=template0", "--", self.name)
        count = self.sql("""SELECT count(*) FROM pg_class c JOIN pg_namespace n
            ON n.oid = c.relnamespace WHERE n.nspname <> 'information_schema'
            AND n.nspname NOT LIKE 'pg_%' AND c.relkind IN ('r','p','v','m','S','f');""")
        if int(count):
            raise SnapshotError(f"Database {self.name!r} is not empty; use a new database")
        with source.open("rb") as stream:
            run(self.base + ["pg_restore", "-U", self.user, "-d", self.name,
                             "--single-transaction", "--exit-on-error", "--no-owner",
                             "--no-privileges"], root=self.root, stdin=stream)


def check_storage(manifest, base):
    for file in manifest["database"]["files"]:
        key = safe_path(file["key"])
        path = base.joinpath(*key.parts)
        if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(base.resolve())
                or path.stat().st_size != file["size"]):
            raise SnapshotError(f"Missing/invalid database file: {key}")


def validate_manifest(manifest):
    if manifest.get("format") != FORMAT:
        raise SnapshotError("Unsupported snapshot format")
    files = manifest.get("files", {})
    required = {f"{SNAPSHOT}/database.dump", f"{SNAPSHOT}/runtime.json",
                "docker-compose.yml", "scripts/portable.py", "web/package-lock.json",
                "web/app/layout.tsx", "services/api/uv.lock", "services/api/app/main.py",
                "services/api/app/models/__init__.py"}
    if not required <= files.keys():
        raise SnapshotError("Snapshot is missing required application files")
    for name in files:
        safe_path(name)
    for file in manifest["database"]["files"]:
        name = f"services/api/storage/{safe_path(file['key'])}"
        if name not in files or files[name]["size"] != file["size"]:
            raise SnapshotError(f"Snapshot is missing a database file: {name}")


def verify_archive(archive):
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = set()
        for member in members:
            safe_path(member.name)
            if not member.isfile() or member.name in names:
                raise SnapshotError(f"Invalid/duplicate archive member: {member.name}")
            names.add(member.name)
        if MANIFEST not in names:
            raise SnapshotError("Archive has no Tenara manifest")
        manifest = json.load(tar.extractfile(MANIFEST))
        validate_manifest(manifest)
        if names != set(manifest["files"]) | {MANIFEST}:
            raise SnapshotError("Archive contents do not match the manifest")
        for member in members:
            if member.name == MANIFEST:
                continue
            expected = manifest["files"][member.name]
            with tar.extractfile(member) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if member.size != expected["size"] or digest != expected["sha256"]:
                raise SnapshotError(f"Checksum mismatch: {member.name}")
    return manifest


def verify_tree(root=ROOT):
    manifest = json.loads((root / MANIFEST).read_text())
    validate_manifest(manifest)
    for name, expected in manifest["files"].items():
        path = root / name
        if (not path.is_file() or path.is_symlink()
                or not path.resolve().is_relative_to(root.resolve())
                or path.stat().st_size != expected["size"] or sha256(path) != expected["sha256"]):
            raise SnapshotError(f"Missing/changed snapshot file: {name}")
    check_storage(manifest, root / "services/api/storage")
    return manifest


def verify_database(db, manifest):
    actual = json.loads(db.sql("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
                               + db.metadata_sql() + "\nCOMMIT;"))
    for key in ("tables", "migrations", "files"):
        if actual[key] != manifest["database"][key]:
            raise SnapshotError(f"Restored database differs from snapshot: {key}")


def copy_file(source, destination):
    if source.is_symlink() or not source.is_file():
        raise SnapshotError(f"Only regular files can be packaged: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = sha256(source)
    shutil.copy2(source, destination)
    if sha256(destination) != before or sha256(source) != before:
        raise SnapshotError(f"File changed during export; stop app/worker and retry: {source}")


def export_snapshot(args):
    output = args.output.resolve()
    if output.exists():
        raise SnapshotError(f"Output already exists: {output}")
    db = Database(args.database, args.compose_project)
    storage = storage_root(args.storage_dir)
    print(f"Exporting Compose database {db.name!r} and the current working tree...", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tenara-export-") as tmp:
        staging = Path(tmp)
        payload = staging / SNAPSHOT
        payload.mkdir()
        for path in source_files():
            copy_file(path, staging / path.relative_to(ROOT))
        with db.snapshot() as metadata:
            db.dump(payload / "database.dump", metadata.pop("snapshot"))
            manifest = {"format": FORMAT, "created_at": datetime.now(UTC).isoformat(),
                        "postgres_major": db.major(), "database": metadata,
                        "browser_state": "fresh", "models_included": args.include_models}
            check_storage(manifest, storage)
            if storage.exists():
                for path in sorted(storage.rglob("*")):
                    if path.is_file() or path.is_symlink():
                        copy_file(path, staging / "services/api/storage" / path.relative_to(storage))
        if args.include_models:
            models = ROOT / "services/api/models"
            if not models.is_dir():
                raise SnapshotError("--include-models requested, but services/api/models is absent")
            for path in sorted(models.rglob("*")):
                if path.is_file() or path.is_symlink():
                    copy_file(path, staging / "services/api/models" / path.relative_to(models))
        env = environment()
        (payload / "runtime.json").write_text(json.dumps(
            {key: env[key] for key in sorted(RUNTIME_KEYS) if key in env}, indent=2) + "\n")
        if (ROOT / ".git").exists():
            manifest["git_commit"] = run(["git", "rev-parse", "HEAD"], capture_output=True,
                                         text=True).stdout.strip()
            manifest["working_tree_included"] = True
        manifest["files"] = {
            path.relative_to(staging).as_posix(): {"size": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(staging.rglob("*")) if path.is_file()
        }
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        validate_manifest(manifest)
        partial = output.with_name(output.name + ".partial")
        try:
            with tarfile.open(partial, "w:gz", compresslevel=6) as tar:
                for path in sorted(staging.rglob("*")):
                    if path.is_file():
                        tar.add(path, arcname=path.relative_to(staging).as_posix(), recursive=False)
            verify_archive(partial)
            partial.replace(output)
        finally:
            partial.unlink(missing_ok=True)
    print(f"Snapshot verified: {output} ({output.stat().st_size / 1024**2:.1f} MiB)")
    print(f"{len(metadata['tables'])} tables; {len(manifest['files'])} files; browser state: fresh")


def unpack(args):
    manifest = verify_archive(args.archive)
    destination = args.destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise SnapshotError("Unpack destination must be a new or empty directory")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.archive, "r:gz") as tar:
        tar.extractall(destination, filter="data")
    verify_tree(destination)
    print(f"Unpacked and verified {len(manifest['files'])} files at {destination}")
    print("Next: docker compose up -d db; python3 scripts/portable.py restore")


def configure(db):
    target = ROOT / ".env"
    if target.exists():
        print("Existing .env kept; check DATABASE_URL, STORAGE_DIR, and local API URL.")
        return
    runtime = json.loads((ROOT / SNAPSHOT / "runtime.json").read_text())
    if not set(runtime) <= RUNTIME_KEYS:
        raise SnapshotError("Unexpected setting in snapshot runtime configuration")
    from urllib.parse import quote
    values = {
        "APP_ENV": "development",
        "DATABASE_URL": f"postgresql+psycopg://{quote(db.user, safe='')}:tenara@localhost:5432/{quote(db.name, safe='')}",
        "TEST_DATABASE_URL": "postgresql+psycopg://tenara:tenara@localhost:5432/tenara_test",
        "STORAGE_DIR": "./storage", "NEXT_PUBLIC_API_URL": "http://localhost:8000",
        "JWT_SECRET": secrets.token_urlsafe(48), "FILE_URL_SECRET": secrets.token_urlsafe(48),
        **runtime,
    }
    # Password above matches the bundled compose file, not a credential from the source computer.
    with target.open("x") as stream:
        stream.write("# Local configuration generated by Tenara restore.\n")
        for key, value in values.items():
            stream.write(f"{key}={json.dumps(value)}\n")
    target.chmod(0o600)
    print("Created local .env. Add an AI provider key there to run new AI jobs.")


def restore(args):
    manifest = verify_tree()
    db = Database(args.database, args.compose_project)
    if db.major() != manifest["postgres_major"]:
        raise SnapshotError(f"Use PostgreSQL {manifest['postgres_major']} (bundled Docker image)")
    db.restore(ROOT / SNAPSHOT / "database.dump")
    verify_database(db, manifest)
    configure(db)
    print(f"Restored and verified database {db.name!r}: all rows, IDs, files and migrations match.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", help="Docker Compose project name (normally automatic)")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="Export current application + database + files")
    export.add_argument("--output", type=Path, default=ROOT / "backups" /
                        f"tenara-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz")
    export.add_argument("--database", help="Compose database name (default: POSTGRES_DB)")
    export.add_argument("--storage-dir", help="Storage root; relative paths resolve from services/api")
    export.add_argument("--include-models", action="store_true", help="Also bundle local ML models")
    extract = sub.add_parser("unpack", help="Verify archive and unpack into a new project directory")
    extract.add_argument("archive", type=Path)
    extract.add_argument("--destination", type=Path, required=True)
    load = sub.add_parser("restore", help="Restore unpacked snapshot into an empty Compose database")
    load.add_argument("--database", help="Compose database name (default: POSTGRES_DB)")
    verify = sub.add_parser("verify", help="Verify an archive, or the unpacked project")
    verify.add_argument("archive", type=Path, nargs="?")
    verify.add_argument("--database", help="Also compare every database table with the snapshot")
    args = parser.parse_args()
    try:
        if args.command == "export":
            export_snapshot(args)
        elif args.command == "unpack":
            unpack(args)
        elif args.command == "restore":
            restore(args)
        else:
            if args.archive and args.database:
                raise SnapshotError("--database compares an unpacked project; omit the archive argument")
            manifest = verify_archive(args.archive) if args.archive else verify_tree()
            if args.database:
                db = Database(args.database, args.compose_project)
                verify_database(db, manifest)
            print(f"Verified: {len(manifest['files'])} files, {len(manifest['database']['tables'])} tables")
    except (SnapshotError, OSError, ValueError, KeyError, tarfile.TarError,
            subprocess.SubprocessError) as exc:
        print(f"Snapshot failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
