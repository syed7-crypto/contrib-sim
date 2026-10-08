import json
import unittest
from unittest.mock import patch

from app.analyzer import parse_plan
from app.gemma import OllamaClient
from app.main import DEFAULT_OFFLINE_RESPONSE
from app.prompts import build_prompt


VALID_RESPONSE = {
    "issue_summary": "Validate input before parsing.",
    "relevant_files": [{"path": "src/parser.py", "reason": "Performs parsing."}],
    "implementation_plan": ["Reject empty input before parsing."],
    "tests": ["Add an empty-input test."],
    "risks": ["Avoid changing behavior for valid input."],
}


class Phase1Tests(unittest.TestCase):
    def test_prompt_includes_evidence_and_issue(self):
        prompt = build_prompt("src/parser.py", "Validate empty input")
        self.assertIn("src/parser.py", prompt)
        self.assertIn("Validate empty input", prompt)
        self.assertIn('"implementation_plan"', prompt)

    def test_valid_response_is_parsed(self):
        plan = parse_plan(json.dumps(VALID_RESPONSE))
        self.assertEqual(plan.issue_summary, "Validate input before parsing.")
        self.assertEqual(plan.relevant_files[0]["path"], "src/parser.py")

    def test_offline_sample_matches_output_contract(self):
        plan = parse_plan(json.dumps(DEFAULT_OFFLINE_RESPONSE))
        self.assertEqual(plan.relevant_files[0]["path"], "src/parser.py")
        self.assertTrue(plan.tests)

    def test_missing_field_is_rejected(self):
        response = dict(VALID_RESPONSE)
        del response["risks"]
        with self.assertRaisesRegex(ValueError, "Missing required fields"):
            parse_plan(json.dumps(response))

    @patch("app.gemma.request.urlopen")
    def test_ollama_client_sends_json_request(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"response": '{"ok": true}'}).encode()

        result = OllamaClient(model="test-model").generate("hello")

        self.assertEqual(result, '{"ok": true}')
        sent_request = urlopen.call_args.args[0]
        sent_payload = json.loads(sent_request.data.decode())
        self.assertEqual(sent_payload["model"], "test-model")
        self.assertFalse(sent_payload["stream"])
        self.assertEqual(sent_payload["format"], "json")


if __name__ == "__main__":
    unittest.main()
