import os
import sys
from django.apps import AppConfig
import dspy


class CplatformioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cPlatformIO'

    def ready(self):
        from cPlatformIO.src.PlatformSetting import PlatformSettings

        lm = dspy.LM(
            api_base=f"http://{PlatformSettings.llm_host}:{PlatformSettings.llm_port}",
            model="ollama_chat/distil-qwen3-4b-text2sql",
            temperature=0.0
        )

        # Configure ONLY ONCE
        if not getattr(dspy.settings, "configured", False):
            dspy.configure(lm=lm)
            print("[OK] DSPy configured at startup")

        is_runserver = "runserver" in sys.argv
        if is_runserver and os.environ.get("RUN_MAIN") != "true":
            print("[CplatformioConfig.ready] Skipping MCP init in reloader parent process")
            return

        from cPlatformIO.src import Cutilinit, McpclInit

        try:
            from yantraAgent.src.subAgents.sqlAgent.schemaRegistration import register_platform_schema
            register_platform_schema()
        except ImportError:
            pass

        try:
            Cutilinit.update_commonutils_config()
        except Exception as e:
            print(f"[CplatformioConfig.ready] CommonUtils init note: {e}")

        try:
            ret, msg = McpclInit.update_mcpclient_config()
            if ret:
                print(f"[CplatformioConfig.ready] MCP init COMPLETE: {msg}")
                return
        except Exception as e:
            msg = str(e)

        strict = bool(getattr(PlatformSettings.get_config().mcp_config, "strict_startup", False))
        print(f"[CplatformioConfig.ready] MCP init status (strict={strict}): {msg}")
        if strict:
            raise RuntimeError(f"[CplatformioConfig.ready] Fatal MCP dependency failed - server startup aborted. Reason: {msg}")
        print("[CplatformioConfig.ready] PlatformOps started successfully.")
