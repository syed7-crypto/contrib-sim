"""Small, bounded GitHub collector for the Phase 2 prototype."""

import base64
import json
import re
from dataclasses import dataclass
from urllib import error, parse, request


class GitHubError(RuntimeError):
    """Raised when GitHub data cannot be collected."""


@dataclass(frozen=True)
class GitHubTarget:
    owner: str
    repository: str
    issue_number: int


def parse_github_urls(repository_url: str, issue_url: str) -> GitHubTarget:
    """Validate matching public GitHub repository and issue URLs."""

    repo_parts = _github_path(repository_url)
    issue_parts = _github_path(issue_url)
    if len(repo_parts) < 2 or len(issue_parts) < 4 or issue_parts[2] != "issues":
        raise ValueError("Use a GitHub repository URL and an issue URL.")
    if repo_parts[:2] != issue_parts[:2]:
        raise ValueError("The repository and issue URLs must point to the same repository.")
    try:
        issue_number = int(issue_parts[3])
    except ValueError as exc:
        raise ValueError("The issue URL must contain a numeric issue number.") from exc
    if issue_number <= 0:
        raise ValueError("The issue number must be positive.")
    return GitHubTarget(repo_parts[0], repo_parts[1], issue_number)


def _github_path(value: str) -> list[str]:
    parsed = parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        raise ValueError("URLs must use github.com.")
    return [part for part in parsed.path.strip("/").split("/") if part]


@dataclass
class GitHubCollector:
    """Collect issue data and a deliberately small repository context."""

    api_url: str = "https://api.github.com"
    max_files: int = 8
    max_file_chars: int = 12000
    timeout: float = 20.0

    def collect(self, target: GitHubTarget) -> tuple[str, str]:
        repository = self._get(f"/repos/{target.owner}/{target.repository}")
        issue = self._get(f"/repos/{target.owner}/{target.repository}/issues/{target.issue_number}")
        branch = repository.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise GitHubError("GitHub repository did not provide a default branch.")

        tree = self._get(
            f"/repos/{target.owner}/{target.repository}/git/trees/{parse.quote(branch, safe='')}?recursive=1"
        )
        entries = tree.get("tree", [])
        if not isinstance(entries, list):
            raise GitHubError("GitHub returned an invalid repository tree.")

        selected = select_context_files(entries, self.max_files, format_issue(issue))
        files = []
        for path in selected:
            content = self._get(
                f"/repos/{target.owner}/{target.repository}/contents/{parse.quote(path, safe='/')}?ref={parse.quote(branch)}"
            )
            file_content = limit_content(decode_content(content), self.max_file_chars)
            files.append(
                {
                    "path": path,
                    "language": detect_language(path),
                    "line_count": str(file_content.count("\n") + 1),
                    "content": file_content,
                }
            )

        return format_repository_context(repository, issue, branch, files), format_issue(issue)

    def _get(self, path: str) -> dict:
        endpoint = f"{self.api_url.rstrip('/')}{path}"
        http_request = request.Request(
            endpoint,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "contrib-sim",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(f"GitHub returned HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise GitHubError("Could not connect to the GitHub API.") from exc
        except json.JSONDecodeError as exc:
            raise GitHubError("GitHub returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise GitHubError("GitHub returned an unexpected response.")
        return data


def select_context_files(entries: list[dict], max_files: int = 8, issue_text: str = "") -> list[str]:
    """Select likely evidence files deterministically from a Git tree."""

    issue_terms = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", issue_text.lower()))
    stop_words = {"the", "and", "for", "with", "from", "that", "this", "issue", "add", "fix"}
    issue_terms -= stop_words
    candidates = []
    for entry in entries:
        path = entry.get("path")
        if entry.get("type") != "blob" or not isinstance(path, str):
            continue
        lower = path.lower()
        if any(part in lower.split("/") for part in ("node_modules", ".git", "dist", "build", "vendor")):
            continue
        name = lower.rsplit("/", 1)[-1]
        extension = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        is_readme = name.startswith("readme")
        is_config = name in {"pyproject.toml", "package.json", "requirements.txt", "setup.py", "cargo.toml", "go.mod"}
        is_code = extension in {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".h"}
        is_test = "test" in name or "tests" in lower.split("/")
        if is_readme:
            priority = 0
        elif is_config:
            priority = 1
        elif is_test:
            priority = 2
        elif is_code:
            priority = 3
        else:
            continue
        path_terms = set(re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", lower.replace("_", " ")))
        keyword_matches = len(issue_terms & path_terms)
        candidates.append((-keyword_matches, priority, len(path), path))
    return [path for _, _, _, path in sorted(candidates)[:max_files]]


def decode_content(content_response: dict) -> str:
    """Decode a GitHub contents API response into readable text."""

    encoded = content_response.get("content")
    if not isinstance(encoded, str):
        return "[File content unavailable]"
    try:
        return base64.b64decode(encoded.replace("\n", "")).decode("utf-8", errors="replace")
    except (ValueError, base64.binascii.Error):
        return "[File content could not be decoded]"


def limit_content(content: str, max_chars: int) -> str:
    """Keep individual files from overwhelming the reasoning prompt."""

    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n[File content truncated by ContribSim]"


def detect_language(path: str) -> str:
    """Return a simple language label for context metadata."""

    extension = path.lower().rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    return {
        "py": "Python",
        "js": "JavaScript",
        "jsx": "JavaScript",
        "ts": "TypeScript",
        "tsx": "TypeScript",
        "go": "Go",
        "rs": "Rust",
        "java": "Java",
        "rb": "Ruby",
        "php": "PHP",
        "c": "C",
        "cpp": "C++",
        "h": "C/C++ header",
        "md": "Markdown",
        "toml": "TOML",
        "json": "JSON",
        "yml": "YAML",
        "yaml": "YAML",
    }.get(extension, "Unknown")


def format_repository_context(repository: dict, issue: dict, branch: str, files: list[dict[str, str]]) -> str:
    """Create bounded, labeled evidence for the reasoning prompt."""

    lines = [
        f"Repository: {repository.get('full_name', 'unknown')}",
        f"Default branch: {branch}",
        f"Repository description: {repository.get('description') or 'Not provided'}",
        "",
        "Issue:",
        f"Title: {issue.get('title', 'Untitled')}",
        f"State: {issue.get('state', 'unknown')}",
        str(issue.get("body") or "No issue description provided."),
        "",
        "Selected files:",
    ]
    for file in files:
        metadata = f"{file.get('language', 'Unknown')}, {file.get('line_count', '?')} lines"
        lines.extend([f"--- {file['path']} ({metadata}) ---", file["content"], ""])
    return "\n".join(lines)


def format_issue(issue: dict) -> str:
    """Create the issue input passed separately to the reasoning prompt."""

    return "\n".join(
        [
            f"Title: {issue.get('title', 'Untitled')}",
            f"State: {issue.get('state', 'unknown')}",
            str(issue.get("body") or "No issue description provided."),
        ]
    )
