import copy
import json
import unittest

from app.analyzer import parse_plan
from app.grounding import validate_plan_grounding
from app.review import review_contribution_plan


CONTEXT = """--- src/parser.py (Python, 4 lines) ---
def parse_input(value):
    return value

--- tests/test_parser.py (Python, 3 lines) ---
def test_valid_input():
    assert parse_input('value') == 'value'
"""


PLAN = {
    "issue_understanding": {
        "summary": "Validate empty parser input.",
        "expected_behavior": "Empty input is rejected before parsing.",
        "acceptance_criteria": ["Add validation for empty input before parsing."],
    },
    "relevant_files": [
        {
            "path": "src/parser.py",
            "reason": "Contains parsing logic.",
            "attention": "Add validation at the parser entry point.",
        },
        {
            "path": "tests/test_parser.py",
            "reason": "Contains parser tests.",
            "attention": "Add empty-input coverage.",
        },
    ],
    "implementation_approach": ["Add validation before parsing."],
    "tests": [
        {
            "path": "tests/test_parser.py",
            "purpose": "Verify empty input is rejected.",
            "change": "Add an empty-input test.",
        }
    ],
    "risks_unknowns": [],
    "contributor_checklist": ["Run parser tests."],
}


def make_plan(value=PLAN):
    return parse_plan(json.dumps(value))


def make_grounding(plan, context=CONTEXT, issue="Add validation for empty input before parsing."):
    return validate_plan_grounding(plan, context, issue)


class ContributionReviewTests(unittest.TestCase):
    def test_strong_plan_is_ready(self):
        plan = make_plan()
        review = review_contribution_plan(plan, make_grounding(plan), CONTEXT)
        self.assertEqual(review.overall_status, "ready")
        self.assertGreaterEqual(review.readiness_score, 80)
        self.assertTrue(review.strengths)

    def test_missing_tests_is_not_ready(self):
        value = copy.deepcopy(PLAN)
        value["tests"] = []
        plan = make_plan(value)
        review = review_contribution_plan(plan, make_grounding(plan), CONTEXT)
        self.assertEqual(review.overall_status, "not_ready")
        self.assertTrue(review.test_gaps)
        self.assertLess(review.readiness_score, 80)

    def test_unsupported_file_prevents_ready(self):
        value = copy.deepcopy(PLAN)
        value["relevant_files"].append(
            {"path": "src/missing.py", "reason": "Parser helper.", "attention": "Modify it."}
        )
        plan = make_plan(value)
        grounding = make_grounding(plan)
        review = review_contribution_plan(plan, grounding, CONTEXT)
        self.assertEqual(review.overall_status, "not_ready")
        self.assertTrue(review.grounding_concerns)

    def test_unverified_assumption_needs_review(self):
        value = copy.deepcopy(PLAN)
        value["implementation_approach"] = ["Update `missing_function()` before parsing."]
        plan = make_plan(value)
        grounding = make_grounding(plan)
        review = review_contribution_plan(plan, grounding, CONTEXT)
        self.assertEqual(review.overall_status, "needs_review")
        self.assertTrue(review.grounding_concerns)

    def test_insufficient_evidence_is_not_ready(self):
        plan = make_plan()
        grounding = make_grounding(plan, "Repository: example/project", "Add validation for empty input.")
        review = review_contribution_plan(plan, grounding, "Repository: example/project")
        self.assertEqual(review.overall_status, "not_ready")
        self.assertTrue(any("insufficient" in issue.lower() for issue in review.issues))

    def test_status_and_score_are_consistent(self):
        plan = make_plan()
        review = review_contribution_plan(plan, make_grounding(plan), CONTEXT)
        self.assertEqual(review.overall_status, "ready")
        self.assertGreaterEqual(review.readiness_score, 80)

        value = copy.deepcopy(PLAN)
        value["tests"] = []
        not_ready_plan = make_plan(value)
        not_ready = review_contribution_plan(not_ready_plan, make_grounding(not_ready_plan), CONTEXT)
        self.assertEqual(not_ready.overall_status, "not_ready")
        self.assertLess(not_ready.readiness_score, 80)


if __name__ == "__main__":
    unittest.main()
