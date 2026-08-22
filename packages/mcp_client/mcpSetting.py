import requests
from typing import Dict, Any, List, Optional
from langchain_ollama import ChatOllama
from dataclasses import dataclass, field
from llama_index.core.settings import Settings
from llama_index.embeddings.ollama import OllamaEmbedding
import redis


@dataclass
class llm_params:
    temperature: float = 0.0
    num_ctx: int = 0
    timeout: int = 0
    num_predict: int = 0
    keep_alive: int = 0
    format: str = ''


@dataclass
class llm_setting:
    llm_model_name: str = ''
    llm_model_host: str = ''
    llm_model_port: str = ''
    llm_params: llm_params = field(default_factory=llm_params)
    llm_config: Optional[ChatOllama] = None
    param_llm_config: Optional[ChatOllama] = None

    def _build_llm_instances(self):
        base_url = f"http://{self.llm_model_host}:{self.llm_model_port}"
        p = self.llm_params
        ollama_kwargs = dict(
            base_url    = base_url,
            model       = self.llm_model_name,
            temperature = p.temperature,
            format      = p.format,
            timeout     = p.timeout,
            num_predict = p.num_predict,
            num_ctx     = p.num_ctx,
            keep_alive  = p.keep_alive,
        )
        self.llm_config       = ChatOllama(**ollama_kwargs)
        self.param_llm_config = ChatOllama(**ollama_kwargs)


@dataclass
class redis_config:
    redis_server_ip: str = ''
    redis_server_port: int = 0
    redis_pool: Optional[redis.ConnectionPool] = None


@dataclass
class mcp:
    mcp_url: str = ''
    mcp_tools: str = ''
    mcp_tool_dict: Dict[str, Any] = field(default_factory=dict)
    intent: List[str] = field(default_factory=list)
    tool_list: List[str] = field(default_factory=list)
    intent_desc: Dict[str, Any] = field(default_factory=dict)
    intent_list: List[Dict[str, str]] = field(default_factory=list)
    intent_classifier_flag: bool = False
    log_file_name: str = ''

@dataclass
class report_info:
    report_url: str = ''
    report_queue: str = ''
    template_name: str = ''


@dataclass
class embedding:
    embed_model: str = 'dengcao/Qwen3-Embedding-0.6B:Q8_0'
    threshold_cutoff: float = 0.65
    embed_dim: int = 768
    top_similarity_k: int = 3



@dataclass
class postgres:
    postgres_database: str = ''
    postgres_host: str = ''
    postgres_password: str = ''
    postgres_port: int = 5432
    postgres_user: str = ''


@dataclass
class dspy_guardrail_setting:
    program_path: str = ''
    model: Optional[Any] = None   # the loaded/compiled dspy.Predict (or Module) instance
    lm: Optional[Any] = None      # the dspy.LM instance backing the classifier


@dataclass
class mcp_Config:
    app_tz: str = 'Asia/Kolkata'
    log_path: str = ''
    tool_access: str = 'external'
    use_gateway_tools: bool = False
    tool_payload: Dict[str, Any] = field(default_factory=dict)
    llm_setting: llm_setting = field(default_factory=llm_setting)
    redis: redis_config = field(default_factory=redis_config)
    mcp: mcp = field(default_factory=mcp)
    embedding: embedding = field(default_factory=embedding)
    postgres: postgres = field(default_factory=postgres)
    report: report_info = field(default_factory=report_info)
    follow_up_question: bool = False
    flag_meta_data: bool = False
    mcp_platform: str = ''
    chat_response_max_chars: int = 4000
    chat_history_ttl_seconds: int = 30 * 24 * 3600
    chat_history_max_messages: int = 200
    redis_max_connections: int = 10
    guardrails_enabled: bool = False
    guardrails_ai_enabled: bool = False
    guardrails_dspy_enabled: bool = False
    dspy_guardrail: dspy_guardrail_setting = field(default_factory=dspy_guardrail_setting)

class mcpSettingsMeta(type):
    def __getattr__(cls, name):
        config = cls.get_config()
        try:
            return getattr(config, name)
        except AttributeError:
            for field_name in config.__dataclass_fields__:
                nested = getattr(config, field_name)
                if isinstance(nested, dict) and name in nested:
                    return nested[name]
                elif hasattr(nested, name):
                    return getattr(nested, name)
            return None

    def __setattr__(cls, name, value):
        if name == "_instance":
            super().__setattr__(name, value)
            return
        config = cls.get_config()
        if name in config.__dataclass_fields__:
            setattr(config, name, value)
            return
        for field_name in config.__dataclass_fields__:
            nested = getattr(config, field_name)
            if hasattr(nested, name):
                setattr(nested, name, value)
                return
            elif isinstance(nested, dict) and name in nested:
                nested[name] = value
                return
        raise AttributeError(f"'{cls.__name__}' object has no attribute '{name}'")


class mcpSettings(metaclass=mcpSettingsMeta):
    _instance: Optional[mcp_Config] = None

    @classmethod
    def load_config(cls):
        cls._instance = mcp_Config()

    @classmethod
    def get_config(cls):
        if cls._instance is None:
            cls.load_config()
        return cls._instance

    @classmethod
    def initialize_llm(cls) -> bool:
        try:
            base_url = f"http://{cls.llm_model_host}:{cls.llm_model_port}"
            p = cls.get_config().llm_setting.llm_params
            requests.post(
                url=f"{base_url}/api/generate",
                json={
                    "model": cls.llm_model_name,
                    "prompt": "hi",
                    "keep_alive": p.keep_alive,
                    "options": {
                        "num_ctx": p.num_ctx,
                        "temperature": p.temperature,
                    },
                },
                timeout=p.timeout if p.timeout > 0 else None,
            )
            print(f"LLM initialized at {base_url}")
            return True
        except Exception as e:
            print(f"LLM initialization failed: {e}")
            return False

    @classmethod
    def get_fresh_llm(
        cls,
        use_param_llm: bool = False,
        json_format: bool = True,
    ) -> ChatOllama:
        p = cls.get_config().llm_setting.llm_params
        model_name = (
            cls.param_llm_config.model
            if use_param_llm and cls.param_llm_config
            else cls.llm_model_name
        )
        return ChatOllama(
            base_url    = f"http://{cls.llm_model_host}:{cls.llm_model_port}",
            model       = model_name,
            temperature = p.temperature,
            format      = "json" if json_format else None,
            timeout     = p.timeout,
            num_predict = p.num_predict,
            num_ctx     = p.num_ctx,
            keep_alive  = p.keep_alive,
        )