from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_root: Path = Path(__file__).resolve().parents[3]
    database_url: str = "sqlite:///data/platformops.db"
    runtime_dir: Path = Path("data/runtime")
    ansible_dir: Path = Path("ops/ansible")
    service_catalog_path: Path = Path("catalog/services.yaml")
    dependency_catalog_path: Path = Path("catalog/dependencies.yaml")
    observability_catalog_path: Path = Path("catalog/observability.yaml")
    local_mode: bool = True

    model_config = SettingsConfigDict(env_prefix="PLATFORMOPS_", env_file=".env", extra="ignore")

    def resolve(self, value: Path) -> Path:
        if value.is_absolute():
            return value
        return self.project_root / value


settings = Settings()
