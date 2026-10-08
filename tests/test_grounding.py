import unittest

from app.analyzer import parse_plan
from app.grounding import validate_plan_grounding


CONTEXT = """Repository: example/project

Issue:
Title: Validate parser input
Add validation for empty input before parsing.

Selected files:
--- src/parser.py (Python, 5 lines) ---
def parse_input(value):
    return value

--- tests/test_parser.py (Python, 4 lines) ---
def test_valid_input():
    assert parse_input('value') == 'value'

--- README (Markdown, 1 lines) ---
Hello World
"""


BASE_PLAN = {
    "issue_understanding": {
        "summary": "Validate parser input.",
        "expected_behavior": "Empty input is rejected before parsing.",
        "acceptance_criteria": ["Add validation for empty input before parsing."],
    },
    "relevant_files": [
        {
            "path": "src/parser.py",
            "reason": "Contains parsing logic.",
            "attention": "Inspect parse_input.",
        }
    ],
    "implementation_approach": ["Update `parse_input()` in `src/parser.py`."],
    "tests": [
        {
            "path": "tests/test_parser.py",
            "purpose": "Check empty input.",
            "change": "Add a test to the existing parser tests.",
        }
    ],
    "risks_unknowns": [],
    "contributor_checklist": ["Run tests/test_parser.py."],
}


class GroundingTests(unittest.TestCase):
    def test_valid_paths_and_symbols_are_grounded(self):
        grounding = validate_plan_grounding(parse_plan_dict(BASE_PLAN), CONTEXT, "Add validation for empty input before parsing.")
        self.assertEqual(grounding["status"], "grounded")
        self.assertEqual(set(grounding["validated_files"]), {"src/parser.py", "tests/test_parser.py"})
        self.assertFalse(grounding["unsupported_claims"])
        self.assertEqual(len(grounding["acceptance_criteria"]["explicit_in_issue"]), 1)

    def test_invented_file_path_is_unsupported(self):
        plan = dict(BASE_PLAN)
        plan["contributor_checklist"] = ["Update `src/missing.py`."]
        grounding = validate_plan_grounding(parse_plan_dict(plan), CONTEXT, "Add validation for empty input before parsing.")
        self.assertEqual(grounding["status"], "unsupported")
        self.assertEqual(grounding["unsupported_claims"][0]["claim"], "src/missing.py")

    def test_unknown_symbol_is_marked_as_assumption(self):
        plan = dict(BASE_PLAN)
        plan["implementation_approach"] = ["Update `missing_function()` in `src/parser.py`."]
        grounding = validate_plan_grounding(parse_plan_dict(plan), CONTEXT, "Add validation for empty input before parsing.")
        self.assertEqual(grounding["status"], "partially_grounded")
        self.assertEqual(grounding["unverified_assumptions"][0]["claim"], "missing_function()")

    def test_inferred_acceptance_criterion_is_not_explicit(self):
        plan = dict(BASE_PLAN)
        plan["issue_understanding"] = dict(BASE_PLAN["issue_understanding"])
        plan["issue_understanding"]["acceptance_criteria"] = ["No regression in valid-input behavior."]
        grounding = validate_plan_grounding(parse_plan_dict(plan), CONTEXT, "Add validation for empty input before parsing.")
        self.assertEqual(grounding["status"], "partially_grounded")
        self.assertEqual(len(grounding["acceptance_criteria"]["inferred_by_model"]), 1)
        self.assertFalse(grounding["acceptance_criteria"]["explicit_in_issue"])

    def test_root_level_evidence_file_is_validated(self):
        plan = dict(BASE_PLAN)
        plan["relevant_files"] = [
            {"path": "README", "reason": "Repository documentation.", "attention": "Verify the content."}
        ]
        plan["tests"] = [
            {"path": "README", "purpose": "Manual documentation check.", "change": "Compare the content."}
        ]
        grounding = validate_plan_grounding(parse_plan_dict(plan), CONTEXT, "Update README.")
        self.assertIn("README", grounding["validated_files"])


def parse_plan_dict(value):
    import json

    return parse_plan(json.dumps(value))


if __name__ == "__main__":
    unittest.main()
