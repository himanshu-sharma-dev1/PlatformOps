import os
import sys
from django.apps import AppConfig


class CplatformioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cPlatformIO'

    def ready(self):
        try:
            import dspy
            from cPlatformIO.src.PlatformSetting import PlatformSettings
            lm = dspy.LM(
                api_base=f"http://{PlatformSettings.llm_host}:{PlatformSettings.llm_port}",
                model="ollama_chat/distil-qwen3-4b-text2sql",
                temperature=0.0
            )
            if not getattr(dspy.settings, "configured", False):
                dspy.configure(lm=lm)
                print("[OK] DSPy configured at startup")
        except Exception:
            pass

        try:
            from cPlatformIO.src import Cutilinit
            Cutilinit.update_commonutils_config()
        except Exception as e:
            print(f"[PlatformOps.ready] Utility initialization: {e}")

        print("[PlatformOps.ready] PlatformOps started successfully.")
