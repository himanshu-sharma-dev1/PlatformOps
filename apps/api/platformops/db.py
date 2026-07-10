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


engine = create_engine(_database_url(), connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    settings.resolve(settings.runtime_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_schema()


def _migrate_sqlite_schema() -> None:
    """Add columns introduced after initial create_all for existing SQLite volumes."""
    url = _database_url()
    if not url.startswith("sqlite:///"):
        return
    from sqlalchemy import text

    migrations: list[tuple[str, str, str]] = [
        ("clusters", "repo_type", "ALTER TABLE clusters ADD COLUMN repo_type VARCHAR(40) DEFAULT 'github'"),
        ("clusters", "repo_url", "ALTER TABLE clusters ADD COLUMN repo_url VARCHAR(512) DEFAULT ''"),
        ("clusters", "repo_branch", "ALTER TABLE clusters ADD COLUMN repo_branch VARCHAR(120) DEFAULT 'main'"),
        ("clusters", "repo_token", "ALTER TABLE clusters ADD COLUMN repo_token VARCHAR(512) DEFAULT ''"),
        ("clusters", "registry_type", "ALTER TABLE clusters ADD COLUMN registry_type VARCHAR(40) DEFAULT 'dockerhub'"),
        ("clusters", "registry_url", "ALTER TABLE clusters ADD COLUMN registry_url VARCHAR(512) DEFAULT ''"),
        ("clusters", "registry_user", "ALTER TABLE clusters ADD COLUMN registry_user VARCHAR(120) DEFAULT ''"),
        ("clusters", "registry_password", "ALTER TABLE clusters ADD COLUMN registry_password VARCHAR(512) DEFAULT ''"),
        ("service_instances", "external_id", "ALTER TABLE service_instances ADD COLUMN external_id VARCHAR(40) DEFAULT ''"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in migrations:
            try:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing = {r[1] for r in rows}
                if column not in existing:
                    conn.execute(text(ddl))
            except Exception:
                pass
        # Backfill SERV#### for rows missing external_id (cPlatform SERVICE_BASE_IDX = 1000)
        try:
            rows = conn.execute(
                text(
                    "SELECT id FROM service_instances "
                    "WHERE external_id IS NULL OR external_id = '' ORDER BY id"
                )
            ).fetchall()
            for (sid,) in rows:
                external = f"SERV{1000 + int(sid)}"
                conn.execute(
                    text("UPDATE service_instances SET external_id = :ext WHERE id = :id"),
                    {"ext": external, "id": sid},
                )
        except Exception:
            pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
