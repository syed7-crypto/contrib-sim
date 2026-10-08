"""Command-line entry point for the Phase 1 contributor simulator."""

import argparse
import json

from app.analyzer import parse_plan
from app.gemma import OllamaClient, OllamaError
from app.prompts import build_prompt


DEFAULT_CONTEXT = """src/
  parser.py
  models.py
  config.py

tests/
  test_parser.py"""
DEFAULT_ISSUE = "Add validation for empty input before parsing."
DEFAULT_OFFLINE_RESPONSE = {
    "issue_summary": "Validate input before the parser processes it.",
    "relevant_files": [
        {
            "path": "src/parser.py",
            "reason": "This is the likely entry point for input validation and parsing.",
        },
        {
            "path": "tests/test_parser.py",
            "reason": "This test module should cover empty-input behavior.",
        },
    ],
    "implementation_plan": [
        "Add an explicit empty-input check before parsing.",
        "Choose a clear error or validation result consistent with the existing parser API.",
    ],
    "tests": [
        "Add a test confirming empty input is rejected before parsing.",
        "Keep existing valid-input tests passing.",
    ],
    "risks": [
        "The new validation must not change behavior for valid input.",
        "The expected empty-input behavior may depend on the parser's public API.",
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a contribution plan with local Gemma.")
    parser.add_argument("--context", default=DEFAULT_CONTEXT, help="Repository context or a path to a text file.")
    parser.add_argument("--issue", default=DEFAULT_ISSUE, help="Issue description.")
    parser.add_argument("--model", default="gemma4:e4b", help="Ollama model name.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL.")
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


def main() -> int:
    args = build_parser().parse_args()
    prompt = build_prompt(read_context(args.context), args.issue)

    try:
        if args.offline:
            plan = parse_plan(json.dumps(DEFAULT_OFFLINE_RESPONSE))
        else:
            client = OllamaClient(model=args.model, base_url=args.ollama_url)
            plan = parse_plan(client.generate(prompt))
    except (OllamaError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(json.dumps(plan.__dict__, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
