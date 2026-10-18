"""
CosmoSafe Local Dashboard and API Server.

Serves the interactive safety dashboard and REST API endpoints locally
using Python's standard library (http.server). Zero additional dependencies required.

Endpoints:
- GET /                   -> Serves the interactive safety dashboard (HTML)
- GET /api/report         -> Returns data/toxicity_report.json
- GET /api/review         -> Returns reports/toxicity/ingredient_identity_review.json
- GET /api/health         -> Health check JSON
"""

import sys
import json
import http.server
import socketserver
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "data" / "toxicity_report.json"
REVIEW_PATH = PROJECT_ROOT / "reports" / "toxicity" / "ingredient_identity_review.json"
DASHBOARD_PATH = PROJECT_ROOT / "reports" / "toxicity" / "safety_dashboard.html"

# Ensure src in sys.path
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from integration.dashboard_generator import export_dashboard_html


class CosmoSafeHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler serving safety dashboard and JSON APIs."""

    def do_GET(self):
        if self.path in ("/", "/index.html", "/dashboard"):
            if not DASHBOARD_PATH.exists() and REPORT_PATH.exists():
                export_dashboard_html(REPORT_PATH, DASHBOARD_PATH)

            if DASHBOARD_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with DASHBOARD_PATH.open("rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Dashboard not yet generated. Run the pipeline first.")

        elif self.path == "/api/report":
            if REPORT_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                with REPORT_PATH.open("rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Report not found"}).encode())

        elif self.path == "/api/review":
            if REVIEW_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                with REVIEW_PATH.open("rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Review registry not found"}).encode())

        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_data = {
                "service": "CosmoSafe Safety Intelligence API",
                "status": "healthy",
                "report_exists": REPORT_PATH.exists(),
                "review_registry_exists": REVIEW_PATH.exists(),
                "dashboard_exists": DASHBOARD_PATH.exists(),
            }
            self.wfile.write(json.dumps(status_data).encode())

        else:
            super().do_GET()


def run_local_server(port: int = 8080):
    """Run local CosmoSafe dashboard server."""
    if REPORT_PATH.exists():
        export_dashboard_html(REPORT_PATH, DASHBOARD_PATH)

    handler = CosmoSafeHTTPHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n=======================================================")
        print(f"CosmoSafe Local Server running at http://localhost:{port}/")
        print(f"Dashboard: http://localhost:{port}/")
        print(f"Report API: http://localhost:{port}/api/report")
        print(f"Review API: http://localhost:{port}/api/review")
        print(f"Press Ctrl+C to stop.")
        print(f"=======================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down CosmoSafe server...")


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_local_server(port_arg)
