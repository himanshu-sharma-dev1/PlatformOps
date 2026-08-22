import os
import json
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

LOG_DIR = "/var/log/test-service"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "test-service.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

class PlatformOpsTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/health", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "PlatformOpsTest"}).encode())
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            metrics = (
                "# HELP platformops_test_uptime_seconds Uptime in seconds\n"
                "# TYPE platformops_test_uptime_seconds gauge\n"
                "platformops_test_uptime_seconds 120\n"
                "# HELP platformops_test_requests_total Total requests\n"
                "# TYPE platformops_test_requests_total counter\n"
                "platformops_test_requests_total 42\n"
            )
            self.wfile.write(metrics.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "running", "path": self.path}).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        body_str = body.decode(errors="ignore")
        logging.info(f"Received UpdateService POST on {self.path}: {body_str}")
        try:
            config_data = json.loads(body_str) if body_str.startswith("{") else {"raw": body_str}
            os.makedirs("/etc", exist_ok=True)
            with open("/etc/test_service.conf", "w") as f:
                f.write(json.dumps(config_data, indent=2))
            logging.info("Successfully updated /etc/test_service.conf")
        except Exception as e:
            logging.error(f"Error saving config: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "msg": "PlatformOpsTest config updated successfully"}).encode())

    def log_message(self, format, *args):
        logging.info("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 6379))
    logging.info(f"Starting PlatformOpsTest server on port {port}...")
    server = HTTPServer(("0.0.0.0", port), PlatformOpsTestHandler)
    server.serve_forever()
