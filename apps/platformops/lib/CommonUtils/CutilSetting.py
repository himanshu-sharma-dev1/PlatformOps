from typing import Optional
from dataclasses import dataclass, field


@dataclass
class prometheus:
    prometheus_server_ip: str = ''
    prometheus_server_port: str = ''


@dataclass
class mail:
    mail_username: str = ''
    mail_password: str = ''
    mail_host: str = ''
    mail_port: int = 0
    mail_use_tls: bool = True


@dataclass
class repo:
    repo_role: str = ''
    repo_sync_method: str = ''
    base_path: str = ''
    primary_machine_info: dict = field(default_factory=dict)


@dataclass
class Cutil_Config:
    app_tz: str = 'Asia/Kolkata'
    service_url: str = ''
    log_path: str = ''
    mail: mail = field(default_factory=mail)
    prometheus: prometheus = field(default_factory=prometheus)
    repo: repo = field(default_factory=repo)
    

class CutilSettingsMeta(type):
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
            return

    def __setattr__(cls, name, value):
        if name == "_instance":
            # Directly set without triggering get_config()
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


class CutilSettings(metaclass=CutilSettingsMeta):
    _instance: Optional[Cutil_Config] = None

    @classmethod
    def load_config(cls):
        cls._instance = Cutil_Config()

    @classmethod
    def get_config(cls):
        if cls._instance is None:
            cls.load_config()
        return cls._instance