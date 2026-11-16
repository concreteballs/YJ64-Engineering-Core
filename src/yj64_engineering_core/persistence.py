"""Additive SQLite persistence for revisioned YJ64 projects and evidence."""
from __future__ import annotations
import hashlib, json, re, sqlite3, threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Iterable

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-fA-F]{64}$")

def _id(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} must be a valid identifier")

def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Value must be finite JSON-compatible data: {exc}") from exc

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class ProjectSnapshot:
    project_id: str
    revision: int
    payload: dict[str, Any]
    payload_sha256: str
    created_at_utc: str

@dataclass(frozen=True)
class StoredCalculation:
    calculation_id: str
    project_id: str
    project_revision: int
    operation: str
    input_digest_sha256: str
    result: dict[str, Any]
    result_sha256: str
    solver_name: str
    solver_version: str
    dependencies: tuple[dict[str, Any], ...]
    status: str
    created_at_utc: str

@dataclass(frozen=True)
class StoredArtifact:
    artifact_id: str
    project_id: str
    project_revision: int
    media_type: str
    uri: str
    sha256: str | None
    calculation_id: str | None
    status: str
    metadata: dict[str, Any]
    created_at_utc: str

class ProjectStore:
    """Transactional append-only snapshots; artifact bytes remain in caller-owned storage."""
    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.database_path, timeout=30, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        if self.database_path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_info(version INTEGER NOT NULL);
        INSERT INTO schema_info(version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_info);
        CREATE TABLE IF NOT EXISTS projects(
          project_id TEXT PRIMARY KEY, title TEXT NOT NULL, current_revision INTEGER NOT NULL,
          metadata_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots(
          project_id TEXT NOT NULL, revision INTEGER NOT NULL, payload_json TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(project_id,revision), FOREIGN KEY(project_id) REFERENCES projects(project_id));
        CREATE TABLE IF NOT EXISTS calculations(
          calculation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, project_revision INTEGER NOT NULL,
          operation TEXT NOT NULL, input_digest TEXT NOT NULL, result_json TEXT NOT NULL,
          result_sha256 TEXT NOT NULL, solver_name TEXT NOT NULL, solver_version TEXT NOT NULL,
          dependencies_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('current','stale')),
          created_at TEXT NOT NULL, FOREIGN KEY(project_id,project_revision) REFERENCES snapshots(project_id,revision));
        CREATE TABLE IF NOT EXISTS artifacts(
          artifact_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, project_revision INTEGER NOT NULL,
          media_type TEXT NOT NULL, uri TEXT NOT NULL, sha256 TEXT, calculation_id TEXT,
          status TEXT NOT NULL CHECK(status IN ('current','stale')), metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL, FOREIGN KEY(project_id,project_revision) REFERENCES snapshots(project_id,revision),
          FOREIGN KEY(calculation_id) REFERENCES calculations(calculation_id));
        """)
        version = self._db.execute("SELECT version FROM schema_info LIMIT 1").fetchone()[0]
        if version != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported ProjectStore schema version: {version}")

    def close(self) -> None:
        with self._lock: self._db.close()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

    def _tx(self):
        store = self
        class Tx:
            def __enter__(self):
                store._lock.acquire()
                store._db.execute("BEGIN IMMEDIATE")
                return store._db
            def __exit__(self, kind, *_):
                try: store._db.execute("ROLLBACK" if kind else "COMMIT")
                finally: store._lock.release()
        return Tx()

    @staticmethod
    def _component_state(payload: Mapping[str, Any]) -> tuple[dict[str, int], set[str]]:
        raw = payload.get("components", [])
        if isinstance(raw, Mapping): raw = list(raw.values())
        if not isinstance(raw, list): raise ValueError("components must be a list or object")
        revisions, components = {}, {}
        for item in raw:
            if not isinstance(item, Mapping): raise ValueError("each component must be an object")
            cid, rev = item.get("component_id"), item.get("revision")
            _id(cid, "component_id")
            if isinstance(rev, bool) or not isinstance(rev, int) or rev < 1: raise ValueError("component revision must be positive integer")
            if cid in revisions: raise ValueError(f"duplicate component_id: {cid}")
            revisions[cid], components[cid] = rev, item
        stale, changed = set(), True
        while changed:
            changed = False
            for cid, component in components.items():
                if cid in stale: continue
                deps = component.get("dependencies", [])
                if not isinstance(deps, list): raise ValueError("component dependencies must be a list")
                for dep in deps:
                    if not isinstance(dep, Mapping): raise ValueError("dependency must be an object")
                    did = dep.get("component_id")
                    if revisions.get(did) != dep.get("revision") or did in stale:
                        stale.add(cid); changed = True; break
        return revisions, stale

    def create_project(self, project_id: str, title: str, metadata: Mapping[str, Any] | None = None) -> None:
        _id(project_id, "project_id")
        if not isinstance(title, str) or not title.strip(): raise ValueError("title must be non-empty")
        meta, now = _json(dict(metadata or {})), _now()
        with self._tx() as db:
            db.execute("INSERT INTO projects VALUES(?,?,0,?,?,?)", (project_id,title.strip(),meta,now,now))

    def save_snapshot(self, project_id: str, payload: Mapping[str, Any], *, expected_revision: int) -> ProjectSnapshot:
        _id(project_id, "project_id")
        if not isinstance(payload, Mapping): raise TypeError("payload must be a mapping")
        if isinstance(expected_revision,bool) or not isinstance(expected_revision,int) or expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer")
        data, now = dict(payload), _now()
        encoded, digest = _json(data), None
        digest = _sha(encoded)
        revisions, stale_components = self._component_state(data)
        with self._tx() as db:
            row = db.execute("SELECT current_revision FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if row is None: raise KeyError(f"Unknown project: {project_id}")
            if row["current_revision"] != expected_revision:
                raise RuntimeError(f"revision conflict: expected {expected_revision}, current {row['current_revision']}")
            revision = expected_revision + 1
            db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)", (project_id,revision,encoded,digest,now))
            db.execute("UPDATE projects SET current_revision=?,updated_at=? WHERE project_id=?", (revision,now,project_id))
            for calc in db.execute("SELECT calculation_id,dependencies_json FROM calculations WHERE project_id=?", (project_id,)).fetchall():
                deps = json.loads(calc["dependencies_json"])
                if any(revisions.get(d["component_id"]) != d["revision"] or d["component_id"] in stale_components for d in deps):
                    db.execute("UPDATE calculations SET status='stale' WHERE calculation_id=?", (calc["calculation_id"],))
                    db.execute("UPDATE artifacts SET status='stale' WHERE calculation_id=?", (calc["calculation_id"],))
        return ProjectSnapshot(project_id,revision,data,digest,now)

    def get_snapshot(self, project_id: str, revision: int | None = None) -> ProjectSnapshot:
        _id(project_id,"project_id")
        with self._lock:
            if revision is None:
                row = self._db.execute("SELECT s.* FROM snapshots s JOIN projects p USING(project_id) WHERE s.project_id=? AND s.revision=p.current_revision",(project_id,)).fetchone()
            else:
                row = self._db.execute("SELECT * FROM snapshots WHERE project_id=? AND revision=?",(project_id,revision)).fetchone()
        if row is None: raise KeyError(f"Snapshot not found: {project_id} revision={revision}")
        return ProjectSnapshot(row["project_id"],row["revision"],json.loads(row["payload_json"]),row["payload_sha256"],row["created_at"])

    def list_revisions(self, project_id: str) -> tuple[ProjectSnapshot, ...]:
        _id(project_id,"project_id")
        with self._lock: rows=self._db.execute("SELECT * FROM snapshots WHERE project_id=? ORDER BY revision",(project_id,)).fetchall()
        return tuple(ProjectSnapshot(r["project_id"],r["revision"],json.loads(r["payload_json"]),r["payload_sha256"],r["created_at"]) for r in rows)

    def record_calculation(self, *, calculation_id: str, project_id: str, operation: str,
                           input_digest_sha256: str, result: Mapping[str, Any],
                           solver_name: str, solver_version: str,
                           dependencies: Iterable[Mapping[str, Any]] = ()) -> StoredCalculation:
        for value,name in ((calculation_id,"calculation_id"),(project_id,"project_id")): _id(value,name)
        for value,name in ((operation,"operation"),(solver_name,"solver_name"),(solver_version,"solver_version")):
            if not isinstance(value,str) or not value.strip(): raise ValueError(f"{name} must be non-empty")
        if not isinstance(input_digest_sha256,str) or not _SHA.fullmatch(input_digest_sha256): raise ValueError("input_digest_sha256 must be SHA-256")
        if not isinstance(result,Mapping): raise TypeError("result must be a mapping")
        deps=[]
        for dep in dependencies:
            if not isinstance(dep,Mapping): raise TypeError("dependency must be a mapping")
            cid,rev=dep.get("component_id"),dep.get("revision"); _id(cid,"component_id")
            if isinstance(rev,bool) or not isinstance(rev,int) or rev<1: raise ValueError("dependency revision must be positive integer")
            deps.append({"component_id":cid,"revision":rev})
        if len({d["component_id"] for d in deps}) != len(deps): raise ValueError("dependency IDs must be unique")
        result_json,deps_json,now=_json(dict(result)),_json(deps),_now()
        with self._tx() as db:
            project=db.execute("SELECT current_revision FROM projects WHERE project_id=?",(project_id,)).fetchone()
            if project is None or project["current_revision"]<1: raise KeyError(f"Project has no snapshot: {project_id}")
            revision=project["current_revision"]
            snap=db.execute("SELECT payload_json FROM snapshots WHERE project_id=? AND revision=?",(project_id,revision)).fetchone()
            current,stale_ids=self._component_state(json.loads(snap["payload_json"]))
            stale=any(current.get(d["component_id"])!=d["revision"] or d["component_id"] in stale_ids for d in deps)
            result_hash=_sha(result_json); status="stale" if stale else "current"
            db.execute("INSERT INTO calculations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (calculation_id,project_id,revision,operation,input_digest_sha256,result_json,result_hash,solver_name,solver_version,deps_json,status,now))
        return StoredCalculation(calculation_id,project_id,revision,operation,input_digest_sha256,dict(result),result_hash,solver_name,solver_version,tuple(deps),status,now)

    def record_artifact(self, *, artifact_id: str, project_id: str, media_type: str, uri: str,
                        sha256: str | None = None, calculation_id: str | None = None,
                        metadata: Mapping[str, Any] | None = None) -> StoredArtifact:
        _id(artifact_id,"artifact_id"); _id(project_id,"project_id")
        if not isinstance(media_type,str) or not media_type.strip() or not isinstance(uri,str) or not uri.strip(): raise ValueError("media_type and uri must be non-empty")
        if sha256 is not None and (not isinstance(sha256,str) or not _SHA.fullmatch(sha256)): raise ValueError("sha256 must be SHA-256")
        if calculation_id is not None: _id(calculation_id,"calculation_id")
        meta,now=_json(dict(metadata or {})),_now()
        with self._tx() as db:
            project=db.execute("SELECT current_revision FROM projects WHERE project_id=?",(project_id,)).fetchone()
            if project is None or project["current_revision"]<1: raise KeyError(f"Project has no snapshot: {project_id}")
            status="current"
            if calculation_id:
                calc=db.execute("SELECT project_id,status FROM calculations WHERE calculation_id=?",(calculation_id,)).fetchone()
                if calc is None or calc["project_id"]!=project_id: raise KeyError(f"Unknown calculation: {calculation_id}")
                if calc["status"]=="stale": status="stale"
            revision=project["current_revision"]
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?)",(artifact_id,project_id,revision,media_type,uri,sha256,calculation_id,status,meta,now))
        return StoredArtifact(artifact_id,project_id,revision,media_type,uri,sha256,calculation_id,status,dict(metadata or {}),now)

    def list_calculations(self, project_id: str) -> tuple[StoredCalculation, ...]:
        _id(project_id,"project_id")
        with self._lock: rows=self._db.execute("SELECT * FROM calculations WHERE project_id=? ORDER BY created_at,calculation_id",(project_id,)).fetchall()
        return tuple(StoredCalculation(r["calculation_id"],r["project_id"],r["project_revision"],r["operation"],r["input_digest"],json.loads(r["result_json"]),r["result_sha256"],r["solver_name"],r["solver_version"],tuple(json.loads(r["dependencies_json"])),r["status"],r["created_at"]) for r in rows)

    def list_artifacts(self, project_id: str) -> tuple[StoredArtifact, ...]:
        _id(project_id,"project_id")
        with self._lock: rows=self._db.execute("SELECT * FROM artifacts WHERE project_id=? ORDER BY created_at,artifact_id",(project_id,)).fetchall()
        return tuple(StoredArtifact(r["artifact_id"],r["project_id"],r["project_revision"],r["media_type"],r["uri"],r["sha256"],r["calculation_id"],r["status"],json.loads(r["metadata_json"]),r["created_at"]) for r in rows)
