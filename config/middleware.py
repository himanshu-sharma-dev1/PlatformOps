# Import modules
import traceback
from django.utils.deprecation import MiddlewareMixin
from cPlatform.AppLogging import app_logger

class ExceptionLoggingMiddleware(MiddlewareMixin):
    # Stores traceback errors in log file
    def process_exception(self, request, exception):
        error_traceback = traceback.format_exc()
        app_logger.error(f"{str(exception)}\n{error_traceback}")
        return None  