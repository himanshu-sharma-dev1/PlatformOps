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
    glitchtip_base_url: str = "http://65.2.63.24:9008"
    glitchtip_token: str = ""  # set PLATFORMOPS_GLITCHTIP_TOKEN in env
    glitchtip_org_slug: str = "iktara"
    glitchtip_project_map: dict = {
        "AIOrchestrator": "cplatform",
        "cPlatform": "cplatform",
        "TrainingServer": "dtrain",
        "dTrain": "dtrain",
        "InferenceServer": "dinfer",
        "dInfer": "dinfer",
        "optionCopilot": "optioncopilot",
        "ANS": "ans",
        "RAG": "rag",
        "Text2SQL": "text2sql",
        "ASR": "asr",
        "TTS": "tts",
        "ConvCall": "convcall",
        "ConvForm": "convform",
        "MCPServer": "mcpserver",
        "McpProxy": "mcpproxy",
        "Airflow": "airflow",
        "McpGateway": "mcpgateway",
        "AirtelChurn": "airtelchurn",
    }
    loki_base_url: str = "http://localhost:3100"
    loki_write_url: str = "http://localhost:3100"
    prometheus_base_url: str = "http://localhost:9090"
    # LLM — mirrors cPlatform CPLATFORM_LLM_* / CPLATFORM_GROQ_*
    llm_provider: str = "mistral"  # groq | mistral | local
    llm_url: str = ""  # override endpoint (mistral/local); empty = provider default
    llm_model: str = "mistral-medium-2508"
    llm_api_key: str = ""  # primary key for active provider (or mistral fallback)
    mistral_api_key: str = ""  # optional explicit Mistral key
    groq_api_key: str = ""  # cPlatform CPLATFORM_GROQ_API_KEY
    groq_model: str = "llama-3.1-8b-instant"
    llm_max_logs: int = 80
    llm_max_tail_logs: int = 30
    llm_num_ctx: int = 16384
    llm_timeout: int = 120
    # Multiuser bootstrap (seeded when user table is empty)
    bootstrap_admin_email: str = "admin"
    bootstrap_admin_password: str = "admin"
    bootstrap_admin_name: str = "admin"
    public_base_url: str = "http://localhost:9002"
    auth_session_hours: int = 72
    max_users: int = 50

    model_config = SettingsConfigDict(env_prefix="PLATFORMOPS_", env_file=".env", extra="ignore")

    def resolve(self, value: Path) -> Path:
        if value.is_absolute():
            return value
        return self.project_root / value


settings = Settings()
