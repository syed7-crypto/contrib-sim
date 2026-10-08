"""Deterministic evidence-grounding checks for Contributor Plans."""

import re
from typing import Any


_FILE_MARKER = re.compile(r"^---\s+(.+?)(?:\s+\([^)]*\))?\s+---\s*$")
_PATH = re.compile(r"(?<![\w.-])(?:[\w.-]+/)+[\w.-]+")
_BACKTICK = re.compile(r"`([^`]+)`")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(?:\(\))?$")
_WORDS = re.compile(r"[a-z0-9]+")


def extract_evidence_files(repository_context: str) -> dict[str, str]:
    """Extract file paths and their contents from labeled repository context."""

    files: dict[str, str] = {}
    current_path: str | None = None
    current_lines: list[str] = []
    for line in repository_context.splitlines():
        marker = _FILE_MARKER.match(line)
        if marker:
            if current_path is not None:
                files[current_path] = "\n".join(current_lines).strip()
            current_path = marker.group(1).strip()
            current_lines = []
        elif current_path is not None:
            current_lines.append(line)
    if current_path is not None:
        files[current_path] = "\n".join(current_lines).strip()
    return files


def extract_evidence_paths(repository_context: str) -> set[str]:
    """Return paths represented in labeled context and simple tree listings."""

    files = set(extract_evidence_files(repository_context))
    for line in repository_context.splitlines():
        candidate = line.strip().lstrip("- ")
        if _PATH.fullmatch(candidate):
            files.add(candidate)
    return files


def validate_plan_grounding(plan: Any, repository_context: str, issue: str) -> dict[str, Any]:
    """Validate model claims against the exact evidence supplied to the model."""

    evidence_files = extract_evidence_files(repository_context)
    evidence_paths = extract_evidence_paths(repository_context)
    evidence_text = "\n".join(evidence_files.values())
    plan_dict = _plan_to_dict(plan)
    all_text = _flatten_strings(plan_dict)

    mentioned_paths = set()
    for text in all_text:
        mentioned_paths.update(_normalize_paths(text))
        for evidence_path in evidence_paths:
            if re.search(r"(?<![\w.-])" + re.escape(evidence_path) + r"(?![\w.-])", text):
                mentioned_paths.add(evidence_path)
    validated_files = sorted(path for path in mentioned_paths if path in evidence_paths)
    unsupported_claims: list[dict[str, str]] = []
    for path in sorted(mentioned_paths - evidence_paths):
        unsupported_claims.append(
            {
                "type": "file_path",
                "claim": path,
                "reason": "The path is not present in the supplied repository context.",
            }
        )

    unverified_assumptions: list[dict[str, str]] = []
    for text in all_text:
        for token in _BACKTICK.findall(text):
            token = token.strip()
            if "/" in token or not _IDENTIFIER.match(token):
                continue
            symbol = token.removesuffix("()")
            if symbol and symbol not in evidence_text:
                unverified_assumptions.append(
                    {
                        "claim": token,
                        "reason": "The referenced symbol or fact was not found in supplied file content.",
                    }
                )

    acceptance_criteria = plan_dict.get("issue_understanding", {}).get("acceptance_criteria", [])
    explicit_criteria = []
    inferred_criteria = []
    for criterion in acceptance_criteria:
        entry = {"criterion": criterion}
        if _is_explicit_in_issue(criterion, issue):
            explicit_criteria.append(entry)
        else:
            inferred_criteria.append(entry)

    if unsupported_claims:
        status = "unsupported"
    elif unverified_assumptions or inferred_criteria:
        status = "partially_grounded"
    else:
        status = "grounded"

    return {
        "status": status,
        "unsupported_claims": unsupported_claims,
        "unverified_assumptions": _deduplicate(unverified_assumptions),
        "validated_files": validated_files,
        "acceptance_criteria": {
            "explicit_in_issue": explicit_criteria,
            "inferred_by_model": inferred_criteria,
        },
    }


def _plan_to_dict(plan: Any) -> dict[str, Any]:
    if hasattr(plan, "__dict__"):
        return {key: value for key, value in plan.__dict__.items() if key != "grounding"}
    if isinstance(plan, dict):
        return plan
    raise TypeError("plan must be a ContributorPlan or dictionary.")


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    return []


def _normalize_paths(text: str) -> set[str]:
    """Normalize paths extracted from prose punctuation."""

    return {match.rstrip(".,;:!?)]}") for match in _PATH.findall(text)}


def _is_explicit_in_issue(criterion: str, issue: str) -> bool:
    criterion_words = set(_WORDS.findall(criterion.lower()))
    issue_words = set(_WORDS.findall(issue.lower()))
    if not criterion_words:
        return False
    normalized_criterion = " ".join(_WORDS.findall(criterion.lower()))
    normalized_issue = " ".join(_WORDS.findall(issue.lower()))
    if normalized_criterion in normalized_issue:
        return True
    overlap = len(criterion_words & issue_words) / len(criterion_words)
    return len(criterion_words) <= 4 and overlap >= 0.75


def _deduplicate(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for item in items:
        key = (item.get("claim"), item.get("reason"))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
