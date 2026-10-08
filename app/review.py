"""Deterministic Contribution Review and readiness assessment."""

from dataclasses import asdict, dataclass
from typing import Any

from app.grounding import extract_evidence_files


@dataclass
class ContributionReview:
    """Structured review whose score and status are evidence-derived."""

    overall_status: str
    strengths: list[str]
    issues: list[str]
    missing_steps: list[str]
    test_gaps: list[str]
    grounding_concerns: list[str]
    recommendations: list[str]
    readiness_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_contribution_plan(plan: Any, grounding: dict[str, Any], repository_context: str) -> ContributionReview:
    """Review a plan using deterministic checks and hard readiness gates."""

    plan_dict = _plan_to_dict(plan)
    evidence_files = extract_evidence_files(repository_context)
    strengths: list[str] = []
    issues: list[str] = []
    missing_steps: list[str] = []
    test_gaps: list[str] = []
    grounding_concerns: list[str] = []
    recommendations: list[str] = []
    score = 100

    understanding = plan_dict.get("issue_understanding", {})
    if understanding.get("summary") and understanding.get("expected_behavior"):
        strengths.append("The issue has a stated summary and expected behavior.")
    else:
        issues.append("Issue understanding is incomplete.")
        missing_steps.append("Clarify the issue summary and expected behavior.")
        score -= 20

    if understanding.get("acceptance_criteria"):
        strengths.append("Acceptance criteria are present for review.")
    else:
        issues.append("No acceptance criteria were identified.")
        missing_steps.append("Derive or verify acceptance criteria from the issue.")
        score -= 10

    files = plan_dict.get("relevant_files", [])
    if files:
        strengths.append(f"The plan identifies {len(files)} relevant file(s).")
    else:
        issues.append("No relevant files were selected.")
        missing_steps.append("Identify the source and test files that need attention.")
        score -= 25

    approach = plan_dict.get("implementation_approach", [])
    if approach:
        strengths.append("The implementation approach contains actionable planning steps.")
    else:
        issues.append("The implementation approach is empty.")
        missing_steps.append("Describe the implementation steps at planning level.")
        score -= 20

    tests = plan_dict.get("tests", [])
    if tests:
        strengths.append("The plan includes test coverage with purposes and changes.")
    else:
        test_gaps.append("No tests were proposed.")
        missing_steps.append("Add tests for the issue behavior and regression coverage.")
        score -= 30

    checklist = plan_dict.get("contributor_checklist", [])
    if checklist:
        strengths.append("A contributor checklist is present.")
    else:
        missing_steps.append("Add a concise implementation checklist.")
        score -= 10

    evidence_count = len(evidence_files)
    if evidence_count < 2:
        issues.append("Repository evidence is insufficient for a reliable implementation plan.")
        grounding_concerns.append("Fewer than two labeled repository files were supplied.")
        recommendations.append("Collect the relevant source and test files before implementation.")
        score -= 30

    unsupported_claims = grounding.get("unsupported_claims", [])
    if unsupported_claims:
        for claim in unsupported_claims:
            grounding_concerns.append(f"Unsupported claim: {claim.get('claim', 'unknown claim')}.")
        issues.append("The plan references repository paths that are not in the supplied evidence.")
        recommendations.append("Verify every referenced path against the repository before coding.")
        score -= min(50, 25 * len(unsupported_claims))

    assumptions = grounding.get("unverified_assumptions", [])
    if assumptions:
        for assumption in assumptions:
            grounding_concerns.append(f"Unverified assumption: {assumption.get('claim', 'unknown')}.")
        recommendations.append("Verify unconfirmed symbols and repository behavior before implementation.")
        score -= min(25, 10 * len(assumptions))

    if grounding.get("status") == "partially_grounded":
        grounding_concerns.append("Some plan claims or acceptance criteria are only partially grounded.")
        score -= 10
    elif grounding.get("status") == "unsupported":
        grounding_concerns.append("Deterministic grounding marked the plan unsupported.")
        score -= 20

    score = max(0, min(100, score))
    critical_failure = bool(unsupported_claims) or evidence_count < 2 or not tests
    if critical_failure:
        status = "not_ready"
    elif assumptions or grounding.get("status") == "partially_grounded" or score < 80:
        status = "needs_review"
    else:
        status = "ready"

    if status == "ready":
        recommendations.append("Confirm the plan against the issue and begin implementation.")
    elif not recommendations:
        recommendations.append("Resolve the listed issues before implementation.")

    return ContributionReview(
        overall_status=status,
        strengths=_unique(strengths),
        issues=_unique(issues),
        missing_steps=_unique(missing_steps),
        test_gaps=_unique(test_gaps),
        grounding_concerns=_unique(grounding_concerns),
        recommendations=_unique(recommendations),
        readiness_score=score,
    )


def _plan_to_dict(plan: Any) -> dict[str, Any]:
    if hasattr(plan, "__dict__"):
        return plan.__dict__
    if isinstance(plan, dict):
        return plan
    raise TypeError("plan must be a ContributorPlan or dictionary.")


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
