from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    if settings.database_url.startswith("sqlite:///") and not settings.database_url.startswith("sqlite:////"):
        relative_path = Path(settings.database_url[10:])
        database_path = settings.resolve(relative_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{database_path}"
    return settings.database_url


_ENGINE_URL = _database_url()
engine = create_engine(
    _ENGINE_URL,
    connect_args={"check_same_thread": False} if _ENGINE_URL.startswith("sqlite:") else {},
    pool_pre_ping=not _ENGINE_URL.startswith("sqlite:"),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    settings.resolve(settings.runtime_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def _migrate_schema() -> None:
    """Apply additive compatibility columns on SQLite and PostgreSQL.

    ``create_all`` only handles fresh databases.  Production Postgres volumes
    can outlive the ORM model, so every additive column is checked through the
    dialect-neutral SQLAlchemy inspector before issuing ``ALTER TABLE``.  No
    values are backfilled for credential fields; their defaults are empty.
    """
    from sqlalchemy import inspect, text

    migrations: list[tuple[str, str, str]] = [
        ("clusters", "description", "ALTER TABLE clusters ADD COLUMN description TEXT DEFAULT ''"),
        ("clusters", "cluster_type", "ALTER TABLE clusters ADD COLUMN cluster_type VARCHAR(80) DEFAULT 'standalone'"),
        ("clusters", "variant", "ALTER TABLE clusters ADD COLUMN variant VARCHAR(80) DEFAULT ''"),
        ("clusters", "role", "ALTER TABLE clusters ADD COLUMN role VARCHAR(80) DEFAULT ''"),
        ("clusters", "repo_type", "ALTER TABLE clusters ADD COLUMN repo_type VARCHAR(40) DEFAULT 'github'"),
        ("clusters", "repo_url", "ALTER TABLE clusters ADD COLUMN repo_url VARCHAR(512) DEFAULT ''"),
        ("clusters", "repo_branch", "ALTER TABLE clusters ADD COLUMN repo_branch VARCHAR(120) DEFAULT 'main'"),
        ("clusters", "repo_token", "ALTER TABLE clusters ADD COLUMN repo_token VARCHAR(512) DEFAULT ''"),
        ("clusters", "repo_path", "ALTER TABLE clusters ADD COLUMN repo_path VARCHAR(512) DEFAULT ''"),
        ("clusters", "repo_auth", "ALTER TABLE clusters ADD COLUMN repo_auth VARCHAR(40) DEFAULT 'pat'"),
        ("clusters", "registry_type", "ALTER TABLE clusters ADD COLUMN registry_type VARCHAR(40) DEFAULT 'dockerhub'"),
        ("clusters", "registry_url", "ALTER TABLE clusters ADD COLUMN registry_url VARCHAR(512) DEFAULT ''"),
        ("clusters", "registry_user", "ALTER TABLE clusters ADD COLUMN registry_user VARCHAR(120) DEFAULT ''"),
        ("clusters", "registry_password", "ALTER TABLE clusters ADD COLUMN registry_password VARCHAR(512) DEFAULT ''"),
        (
            "clusters",
            "registry_namespace",
            "ALTER TABLE clusters ADD COLUMN registry_namespace VARCHAR(255) DEFAULT ''",
        ),
        ("clusters", "registry_auth", "ALTER TABLE clusters ADD COLUMN registry_auth VARCHAR(40) DEFAULT 'password'"),
        ("clusters", "image_store", "ALTER TABLE clusters ADD COLUMN image_store VARCHAR(120) DEFAULT ''"),
        ("service_instances", "external_id", "ALTER TABLE service_instances ADD COLUMN external_id VARCHAR(40) DEFAULT ''"),
        ("nodes", "provider", "ALTER TABLE nodes ADD COLUMN provider VARCHAR(80) DEFAULT 'dc'"),
        ("nodes", "region", "ALTER TABLE nodes ADD COLUMN region VARCHAR(120) DEFAULT 'local'"),
        ("nodes", "availability_zone", "ALTER TABLE nodes ADD COLUMN availability_zone VARCHAR(120) DEFAULT ''"),
        ("nodes", "auth_mode", "ALTER TABLE nodes ADD COLUMN auth_mode VARCHAR(40) DEFAULT 'ssh_key'"),
        ("nodes", "ssh_secret_ref", "ALTER TABLE nodes ADD COLUMN ssh_secret_ref VARCHAR(512) DEFAULT ''"),
        ("nodes", "host_key_fingerprint", "ALTER TABLE nodes ADD COLUMN host_key_fingerprint VARCHAR(160) DEFAULT ''"),
        ("nodes", "known_hosts_ref", "ALTER TABLE nodes ADD COLUMN known_hosts_ref VARCHAR(512) DEFAULT ''"),
        ("nodes", "monitor_port", "ALTER TABLE nodes ADD COLUMN monitor_port INTEGER DEFAULT 9100"),
        ("nodes", "ingress_ports", "ALTER TABLE nodes ADD COLUMN ingress_ports VARCHAR(512) DEFAULT ''"),
        ("nodes", "cloud_id", "ALTER TABLE nodes ADD COLUMN cloud_id VARCHAR(255) DEFAULT ''"),
        ("nodes", "cloud_instance_id", "ALTER TABLE nodes ADD COLUMN cloud_instance_id VARCHAR(255) DEFAULT ''"),
        ("nodes", "cloud_resource_id", "ALTER TABLE nodes ADD COLUMN cloud_resource_id VARCHAR(255) DEFAULT ''"),
        ("nodes", "cloud_account_id", "ALTER TABLE nodes ADD COLUMN cloud_account_id VARCHAR(255) DEFAULT ''"),
        ("nodes", "cloud_image_id", "ALTER TABLE nodes ADD COLUMN cloud_image_id VARCHAR(255) DEFAULT ''"),
        ("user_info", "permissions", "ALTER TABLE user_info ADD COLUMN permissions TEXT DEFAULT '[]'"),
    ]
    with engine.begin() as conn:
        inspector = inspect(conn)
        table_columns = {
            table: {str(item["name"]) for item in inspector.get_columns(table)}
            for table in inspector.get_table_names()
        }
        for table, column, ddl in migrations:
            existing = table_columns.get(table)
            if existing is None or column in existing:
                continue
            conn.execute(text(ddl))
            # SQLAlchemy's Inspector caches metadata; update the local view so
            # the same startup pass remains idempotent after an ALTER.
            existing.add(column)
        # A few pre-migration development databases used the shorter aliases
        # from the editor.  Preserve those values when the canonical columns
        # are introduced alongside them.
        try:
            cluster_columns = table_columns.get("clusters", set())
            if "type" in cluster_columns and "cluster_type" in cluster_columns:
                conn.execute(
                    text(
                        "UPDATE clusters SET cluster_type = type "
                        "WHERE (cluster_type IS NULL OR cluster_type = '' OR cluster_type = 'standalone') "
                        "AND type IS NOT NULL AND type <> ''"
                    )
                )
        except Exception:
            pass
        try:
            node_columns = table_columns.get("nodes", set())
            aliases = {
                "az": "availability_zone",
                "monitoring_port": "monitor_port",
                "instance_id": "cloud_instance_id",
                "resource_id": "cloud_resource_id",
                "ami_id": "cloud_image_id",
            }
            for source, target in aliases.items():
                if source in node_columns and target in node_columns:
                    conn.execute(
                        text(
                            f"UPDATE nodes SET {target} = {source} "
                            f"WHERE ({target} IS NULL OR {target} = '' OR {target} = 0) "
                            f"AND {source} IS NOT NULL"
                        )
                    )
        except Exception:
            pass
        # Backfill SERV#### for rows missing external_id (cPlatform SERVICE_BASE_IDX = 1000)
        try:
            rows = conn.execute(
                text("SELECT id, external_id FROM service_instances ORDER BY id")
            ).fetchall()
            used: set[str] = set()
            max_seen = 999
            for sid, external_id in rows:
                token = str(external_id or "").strip()
                if token:
                    used.add(token)
                    if token.upper().startswith("SERV"):
                        try:
                            max_seen = max(max_seen, int(token[4:]))
                        except ValueError:
                            pass
            next_num = max_seen + 1
            assigned: set[str] = set()
            for sid, external_id in rows:
                token = str(external_id or "").strip()
                # Preserve the first occurrence of an existing public id but
                # repair duplicate/blank rows before creating the unique index.
                if token and token not in assigned:
                    assigned.add(token)
                    continue
                while f"SERV{next_num}" in used:
                    next_num += 1
                external = f"SERV{next_num}"
                next_num += 1
                used.add(external)
                assigned.add(external)
                conn.execute(
                    text("UPDATE service_instances SET external_id = :ext WHERE id = :id"),
                    {"ext": external, "id": sid},
                )
        except Exception:
            pass
        # Fresh databases get a unique constraint from the ORM model; existing
        # SQLite volumes need an explicit index.  The repair above makes this
        # safe even when older rows contained duplicate external ids.
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_service_instances_external_id "
                    "ON service_instances (external_id)"
                )
            )
        except Exception:
            # A legacy database with an incompatible hand-written schema should
            # remain bootable; allocation still checks ids in application code.
            pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
