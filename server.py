"""Small HTTP adapter and static-file server for the ContribSim frontend."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.github import GitHubCollector, GitHubError, parse_github_urls
from app.main import DEFAULT_CONTEXT, DEFAULT_ISSUE, analyze_context, load_local_env


ROOT = Path(__file__).parent
FRONTEND = ROOT / "frontend"


def analyze_request(payload: dict) -> dict:
    """Adapt the browser request to the existing collection/analysis pipeline."""

    repository_url = payload.get("repository_url")
    issue_url = payload.get("issue_url")
    if not isinstance(repository_url, str) or not isinstance(issue_url, str):
        raise ValueError("repository_url and issue_url are required.")

    offline = os.environ.get("CONTRIBSIM_OFFLINE", "").lower() in {"1", "true", "yes"}
    provider = os.environ.get("CONTRIBSIM_PROVIDER", "gemini")
    model = os.environ.get("CONTRIBSIM_MODEL") or None
    ollama_url = os.environ.get("CONTRIBSIM_OLLAMA_URL", "http://localhost:11434")

    if offline:
        return analyze_context(
            DEFAULT_CONTEXT,
            DEFAULT_ISSUE,
            provider,
            model=model,
            ollama_url=ollama_url,
            offline=True,
        )

    target = parse_github_urls(repository_url, issue_url)
    repository_context, issue, _ = GitHubCollector().collect_with_metadata(target)
    return analyze_context(
        repository_context,
        issue,
        provider,
        model=model,
        ollama_url=ollama_url,
        offline=False,
    )


class ContribSimHandler(BaseHTTPRequestHandler):
    """Serve the static UI and the single JSON API endpoint."""

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send_file(FRONTEND / "index.html", "text/html; charset=utf-8")
            return
        if path in {"/app.js", "/styles.css"}:
            file_path = FRONTEND / path.removeprefix("/")
            content_type = "application/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8"
            self._send_file(file_path, content_type)
            return
        self._send_json({"error": "Not found."}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/analyze":
            self._send_json({"error": "Not found."}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = analyze_request(payload)
        except (ValueError, json.JSONDecodeError, GitHubError, OSError) as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        except Exception as exc:  # Keep provider/network failures as JSON API errors.
            self._send_json({"error": str(exc)}, 502)
            return
        self._send_json(result, 200)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json({"error": "Frontend asset not found."}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, value: dict, status: int) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    load_local_env()
    host = os.environ.get("CONTRIBSIM_HOST", "127.0.0.1")
    port = int(os.environ.get("CONTRIBSIM_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ContribSimHandler)
    print(f"ContribSim running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
