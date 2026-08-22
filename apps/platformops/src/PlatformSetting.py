''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : PlatformSetting.py
* Description       : Functions related to platform setting
*
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 22-May-25 		Vidushi Gandhi		        Created.
* 06-Aug-25 		Sumit Das		            Updated.
*********************************************************************************************************************'''

# Import modules
import os
import yaml
import requests
from dotenv import dotenv_values
from pathlib import Path
from typing import Optional
from django.conf import settings
from dataclasses import dataclass, field
from langchain_ollama import ChatOllama


# ---------------------------------------------Updated data classes----------------------------------------------------#

# --- Configuration Path ---
def _find_config_dir():
    env_dir = os.environ.get('PLATFORMOPS_CONFIG_DIR')
    if env_dir and os.path.exists(env_dir):
        return env_dir
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        cand = parent / 'config'
        if (cand / 'cPlatform_config.yaml').exists():
            return str(cand)
    return str(cur.parents[2] / 'config')

CONFIG_DIR = _find_config_dir()
CPLATFORM_CONFIG_PATH = os.path.join(CONFIG_DIR, 'cPlatform_config.yaml')


@dataclass
class postgres:
    postgres_database: str = ''
    postgres_host: str = ''
    postgres_password: str = ''
    postgres_port: int = 5432
    postgres_user: str = ''

@dataclass
class django:
    django_secret_key: str = ''
    django_debug: bool = False

@dataclass
class llm_params:
    temperature: float = 0.1
    num_ctx: int = 4096
    num_predict: int = 128
    timeout: int = 60
    keep_alive: int = -1
    format: str = 'json'


@dataclass
class mcp:
    mcp_gateway_uri: str = ''
    mcp_server_uri: str = ''


@dataclass
class mcp_config:
    platform_id: str = ''
    intent_flag: bool = False
    follow_up_question: bool = False
    use_gateway_tools: bool = False
    tools_config_path: str = ''
    tool_access: str = 'external'
    flag_meta_data: bool = False
    log_file_name: str = ''
    guardrail_flag: bool = False
    guardrail_ai_flag: bool = False
    guardrail_dspy_flag: bool = False
    strict_startup    :bool =False


@dataclass
class widget_config:
    report_url: str = ''
    report_queue: str = 'cPlatform_dataflow'
    template_name: str = 'airtelTaw/dChatEmail.html'


@dataclass
class prometheus:
    prometheus_server_ip: str = ''
    prometheus_server_port: str = ''


@dataclass
class mail:
    mail_host: str = ''
    mail_port: int = 0
    mail_username: str = ''
    mail_password: str = ''
    mail_use_tls: bool = True
    mail_agent: list[str] = field(default_factory=list)

    def normalize(self):
        if isinstance(self.mail_agent, str):
            self.mail_agent = [m.strip() for m in self.mail_agent.split(",") if m.strip()]


@dataclass
class dataflow_agent_flag:
    dataflow_agent_flag: str = ''


@dataclass
class repo:
    repo_role: str = ''
    repo_sync: str = ''
    master_host: str = ''
    master_path: str = ''
    master_auth_type: str = ''
    master_username: str = ''
    master_password: str = ''
    master_pem_file_name: str = ''
    master_pem_file_text: str = ''


@dataclass
class service:
    deploy_status: str = ''
    service_install: str = ''
    service_version: str = ''
    mcp_url: str = ''
    text2sql_url:str = ''
    gpu_flag: str = ''
    time_zone: str = ''
    cplatform_url: str = ''
    service_ip: str = ''
    service_port: int = 9000


@dataclass
class llm:
    llm_model: str = ''
    llm_host: str = ''
    llm_port: str = ''


@dataclass
class redis:
    redis_server_ip: str = ''
    redis_server_port: str = ''


@dataclass
class celery:
    celery_app: str = ''
    celery_broker: str = ''


@dataclass
class PlatformConfigData:
    postgres: postgres = field(default_factory=postgres)
    django: django = field(default_factory=django)
    mail: mail = field(default_factory=mail)
    dataflow_agent_flag: dataflow_agent_flag = field(default_factory=dataflow_agent_flag)
    repo: repo = field(default_factory=repo)
    llm: llm = field(default_factory=llm)
    llm_params: llm_params = field(default_factory=llm_params)
    celery: celery = field(default_factory=celery)
    redis: redis = field(default_factory=redis)
    prometheus: prometheus = field(default_factory=prometheus)
    service: service = field(default_factory=service)
    mcp: mcp = field(default_factory=mcp)
    mcp_config: mcp_config = field(default_factory=mcp_config)
    widget_config: widget_config = field(default_factory=widget_config)
    intents: list = field(default_factory=list)
    deployment_type: str = ''
    repository_path: str = 'iktara/Repository'
    db_engine: str = 'django.db.backends.sqlite3'
    default_response: str = ''


class PlatformSettingsMeta(type):
    def __getattr__(cls, name):
        try:
            config = cls.get_config()
            # Root fields
            if hasattr(config, name):
                return getattr(config, name)
            # Search every nested dataclass
            for field_name in config.__dataclass_fields__:
                nested = getattr(config, field_name)
                if nested is None:
                    continue
                # dataclass objects
                if hasattr(nested, name):
                    return getattr(nested, name)
                # dicts
                if isinstance(nested, dict) and name in nested:
                    return nested[name]
            raise AttributeError(f"{cls.__name__} has no attribute '{name}'")

        except Exception as e:
            # Never break Django startup
            print(f"[PlatformSettings] __getattr__({name}) failed: {e}")
            return None


class PlatformSettings(metaclass=PlatformSettingsMeta):
    _instance: Optional[PlatformConfigData] = None
    llm: Optional[ChatOllama] = None

    @classmethod
    def fetch_env_data(cls, config):
        env_categories = ['celery', 'postgres', 'redis', 'django', 'mcp', 'llm_params']
        allowed_root_keys = set(PlatformConfigData.__dataclass_fields__.keys())
        env_dict = dict(dotenv_values(settings.ENV_FILE))

        for key, value in env_dict.items():
            match = False
            for category in env_categories:
                if key.startswith(category):
                    if category not in config:
                        config[category] = {}
                    if key == "django_debug":
                        config[category][key] = value.lower() in ("true", "1", "yes")
                    else:
                        config[category][key] = value
                    match = True
                    break
            if not match and key in allowed_root_keys:
                config[key] = value
        return config

    @classmethod
    def load_config(cls):
        with open(CPLATFORM_CONFIG_PATH, "r") as file:
            config_data = yaml.safe_load(file)
        raw = cls.fetch_env_data(config_data['CPLATFORM_CONFIG'])

        valid_fields = set(PlatformConfigData.__dataclass_fields__.keys())
        filtered = {k: v for k, v in raw.items() if k in valid_fields}

        filtered['llm'] = llm(**(raw.get('llm') or {}))
        filtered['llm_params'] = llm_params(**(raw.get('llm_params') or {}))
        filtered['mcp'] = mcp(**(raw.get('mcp') or {}))
        filtered['mcp_config'] = mcp_config(**(raw.get('mcp_config') or {}))
        filtered['widget_config'] = widget_config(**(raw.get('widget') or {}))
        filtered['intents'] = raw.get('intents') or []

        cls._instance = PlatformConfigData(**filtered)

    @classmethod
    def get_config(cls):
        cls.load_config()
        return cls._instance

    @classmethod
    def initialize_llm(cls):
        cfg = cls.get_config()
        host, port, model = cfg.llm.llm_host, cfg.llm.llm_port, cfg.llm.llm_model

        if not host or not port or not model:
            print(f"[PlatformSettings] LLM not fully configured "
                  f"(model={model!r}, host={host!r}, port={port!r}) — skipping init.")
            return None

        base_url = f"http://{host}:{port}"
        llm_conf = cfg.llm_params
        keep_alive = llm_conf.keep_alive if llm_conf.keep_alive else -1

        try:
            requests.post(
                url=f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "hi",
                    "keep_alive": keep_alive,
                    "options": {
                        "num_ctx": llm_conf.num_ctx,
                        "temperature": llm_conf.temperature,
                        "num_predict": llm_conf.num_predict,
                    }
                },
                timeout=llm_conf.timeout if llm_conf.timeout > 0 else None
            )
        except Exception as e:
            print(f"[PlatformSettings] LLM warm-up ping failed (continuing anyway): {e}")

        cls.llm = ChatOllama(
            model=model, base_url=base_url, keep_alive=keep_alive,
            num_ctx=llm_conf.num_ctx, num_predict=llm_conf.num_predict,
            temperature=llm_conf.temperature,
        )

        print(f"Init LLM : PlatformSettings: {cls.llm}")
        return cls.llm

    @classmethod
    def get_llm(cls):
        if cls.llm is None:
            cls.initialize_llm()
        return cls.llm

    @classmethod
    def get_fresh_llm(cls, json_format: bool = True) -> ChatOllama:
        """Build a brand-new ChatOllama client for this call only.

        Do NOT reuse cls.llm across requests that each run on their own
        event loop (e.g. Django sync views calling
        loop.run_until_complete per request) — a cached client's async
        connection is bound to the loop that created it, and reusing it
        after that loop closes throws 'Event loop is closed'.
        """
        cfg = cls.get_config()
        host, port, model = cfg.llm.llm_host, cfg.llm.llm_port, cfg.llm.llm_model
        if not host or not port or not model:
            raise RuntimeError(
                f"[PlatformSettings] LLM not fully configured "
                f"(model={model!r}, host={host!r}, port={port!r})"
            )
        llm_conf = cfg.llm_params
        return ChatOllama(
            base_url=f"http://{host}:{port}",
            model=model,
            temperature=llm_conf.temperature,
            format="json" if json_format else None,
            timeout=llm_conf.timeout,
            num_predict=llm_conf.num_predict,
            num_ctx=llm_conf.num_ctx,
            keep_alive=llm_conf.keep_alive if llm_conf.keep_alive else -1,
        )


    @classmethod
    def update_config(cls):
        with open(CPLATFORM_CONFIG_PATH, "r") as file:
            config_data = yaml.safe_load(file)
        for key, value in config_data.items():
            setattr(cls._instance, key, value)

    @classmethod
    def update_config_data(cls, data):
        with open(CPLATFORM_CONFIG_PATH, "w") as file:
            yaml.safe_dump(data, file)
        cls._instance = None
