"""Repeatable end-to-end evaluation workflow for real GitHub issues."""

import argparse
import json
from pathlib import Path

from app.github import GitHubCollector, GitHubError, parse_github_urls
from app.grounding import extract_evidence_files
from app.gemma import GeminiError, OllamaError
from app.main import analyze_context, load_local_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate ContribSim against a GitHub repository and issue.")
    parser.add_argument("--fixture", required=True, help="Path to an evaluation JSON fixture.")
    parser.add_argument("--provider", choices=("gemini", "ollama"), help="Override the fixture provider.")
    parser.add_argument("--model", help="Override the provider model.")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--offline", action="store_true", help="Use the deterministic sample response after collection.")
    parser.add_argument("--verbose", action="store_true", help="Include issue and evidence diagnostics.")
    return parser


def main() -> int:
    load_local_env()
    args = build_parser().parse_args()
    try:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        repository_url = fixture["repository_url"]
        issue_url = fixture["issue_url"]
        provider = args.provider or fixture.get("provider", "gemini")
        target = parse_github_urls(repository_url, issue_url)
        repository_context, issue = GitHubCollector().collect(target)
        output = analyze_context(
            repository_context,
            issue,
            provider,
            model=args.model or fixture.get("model"),
            ollama_url=args.ollama_url,
            offline=args.offline,
        )
        if args.verbose:
            output["debug"] = {
                "fixture": fixture,
                "issue": issue,
                "selected_files": sorted(extract_evidence_files(repository_context)),
                "evidence_supplied": repository_context,
            }
        print(json.dumps(output, indent=2))
        return 0
    except (OSError, KeyError, json.JSONDecodeError, ValueError, GitHubError, GeminiError, OllamaError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
