from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    if settings.database_url.startswith("sqlite:///") and not settings.database_url.startswith("sqlite:////"):
        relative_path = Path(settings.database_url.removeprefix("sqlite:///"))
        database_path = settings.resolve(relative_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{database_path}"
    return settings.database_url


engine = create_engine(_database_url(), connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    settings.resolve(settings.runtime_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
