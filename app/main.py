"""Command-line entry point for the Phase 1 contributor simulator."""

import argparse
import json
import os
from pathlib import Path

from app.analyzer import parse_plan
from app.gemma import GeminiClient, GeminiError, OllamaClient, OllamaError
from app.github import GitHubCollector, GitHubError, parse_github_urls
from app.grounding import extract_evidence_files, validate_plan_grounding
from app.review import review_contribution_plan
from app.prompts import build_prompt


DEFAULT_CONTEXT = """Repository: sample/project

Selected files:
--- src/parser.py (Python, 1 lines) ---
# Parser implementation supplied as repository evidence.

--- src/models.py (Python, 1 lines) ---
# Model definitions supplied as repository evidence.

--- src/config.py (Python, 1 lines) ---
# Configuration supplied as repository evidence.

--- tests/test_parser.py (Python, 1 lines) ---
# Parser tests supplied as repository evidence."""
DEFAULT_ISSUE = "Add validation for empty input before parsing."
DEFAULT_OFFLINE_RESPONSE = {
    "issue_understanding": {
        "summary": "Validate input before the parser processes it.",
        "expected_behavior": "Empty input should be rejected before parsing begins.",
        "acceptance_criteria": ["Empty input is detected before parser logic runs."],
    },
    "relevant_files": [
        {
            "path": "src/parser.py",
            "reason": "This is the likely entry point for input validation and parsing.",
            "attention": "Inspect the parser entry point and add the validation before parsing.",
        },
        {
            "path": "tests/test_parser.py",
            "reason": "This test module should cover empty-input behavior.",
            "attention": "Add a focused test for empty input while preserving valid-input coverage.",
        },
    ],
    "implementation_approach": [
        "Add an explicit empty-input check before parsing.",
        "Choose a clear error or validation result consistent with the existing parser API.",
    ],
    "tests": [
        {
            "path": "tests/test_parser.py",
            "purpose": "Verify empty input is rejected before parsing.",
            "change": "Add an empty-input test and preserve valid-input tests.",
        }
    ],
    "risks_unknowns": [
        "The new validation must not change behavior for valid input.",
        "The expected empty-input behavior may depend on the parser's public API.",
    ],
    "contributor_checklist": [
        "Inspect the parser entry point and existing error conventions.",
        "Implement validation before parsing.",
        "Add or update focused tests.",
        "Run the relevant test suite.",
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a contribution plan with Gemma.")
    parser.add_argument("--context", default=DEFAULT_CONTEXT, help="Repository context or a path to a text file.")
    parser.add_argument("--issue", default=DEFAULT_ISSUE, help="Issue description.")
    parser.add_argument("--provider", choices=("gemini", "ollama"), default=os.environ.get("CONTRIBSIM_PROVIDER", "gemini"), help="Reasoning provider.")
    parser.add_argument("--model", help="Model name for the selected provider.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument("--repo-url", help="Public GitHub repository URL.")
    parser.add_argument("--issue-url", help="GitHub issue URL in that repository.")
    parser.add_argument("--verbose", action="store_true", help="Include issue and evidence diagnostics in JSON output.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use a deterministic sample response without connecting to Ollama.",
    )
    return parser


def read_context(value: str) -> str:
    """Treat --context as inline text unless it names a readable file."""

    try:
        with open(value, encoding="utf-8") as context_file:
            return context_file.read()
    except (OSError, UnicodeDecodeError):
        return value


def load_local_env(path: str = ".env") -> None:
    """Load simple KEY=VALUE entries without adding a dependency."""

    env_file = Path(path)
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


def analyze_context(
    repository_context: str,
    issue: str,
    provider: str,
    model: str | None = None,
    ollama_url: str = "http://localhost:11434",
    offline: bool = False,
) -> dict:
    """Run plan generation, grounding, and review for supplied evidence."""

    prompt = build_prompt(repository_context, issue)
    if offline:
        plan = parse_plan(json.dumps(DEFAULT_OFFLINE_RESPONSE))
    elif provider == "gemini":
        client = GeminiClient.from_environment(model=model)
        plan = parse_plan(client.generate(prompt))
    else:
        client = OllamaClient(model=model or "gemma4:e4b", base_url=ollama_url)
        plan = parse_plan(client.generate(prompt))

    grounding = validate_plan_grounding(plan, repository_context, issue)
    output = dict(plan.__dict__)
    output["grounding"] = grounding
    output["review"] = review_contribution_plan(plan, grounding, repository_context).to_dict()
    return output


def main() -> int:
    load_local_env()
    args = build_parser().parse_args()

    try:
        if bool(args.repo_url) != bool(args.issue_url):
            raise ValueError("Provide both --repo-url and --issue-url together.")
        if args.repo_url and args.issue_url:
            target = parse_github_urls(args.repo_url, args.issue_url)
            repository_context, issue = GitHubCollector().collect(target)
        else:
            repository_context = read_context(args.context)
            issue = args.issue
        output = analyze_context(
            repository_context,
            issue,
            args.provider,
            model=args.model,
            ollama_url=args.ollama_url,
            offline=args.offline,
        )
    except (GeminiError, GitHubError, OllamaError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    if args.verbose:
        output["debug"] = {
            "issue": issue,
            "selected_files": sorted(extract_evidence_files(repository_context)),
            "evidence_supplied": repository_context,
        }
    print(json.dumps(output, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
