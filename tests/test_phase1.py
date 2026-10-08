import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.analyzer import parse_plan
from app.gemma import GeminiClient, OllamaClient
from app.main import DEFAULT_OFFLINE_RESPONSE, load_local_env
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

    def test_json_is_extracted_from_surrounding_model_text(self):
        response = "Reasoning...\nFinal answer:\n" + json.dumps(VALID_RESPONSE)
        plan = parse_plan(response)
        self.assertEqual(plan.issue_summary, "Validate input before parsing.")

    def test_offline_sample_matches_output_contract(self):
        plan = parse_plan(json.dumps(DEFAULT_OFFLINE_RESPONSE))
        self.assertEqual(plan.relevant_files[0]["path"], "src/parser.py")
        self.assertTrue(plan.tests)

    def test_load_local_env_does_not_override_existing_values(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as env_file:
            env_file.write("TEST_CONTRIBSIM_KEY=from-file\n")
            env_path = env_file.name
        try:
            os.environ.pop("TEST_CONTRIBSIM_KEY", None)
            load_local_env(env_path)
            self.assertEqual(os.environ["TEST_CONTRIBSIM_KEY"], "from-file")
            os.environ["TEST_CONTRIBSIM_KEY"] = "existing"
            load_local_env(env_path)
            self.assertEqual(os.environ["TEST_CONTRIBSIM_KEY"], "existing")
        finally:
            os.environ.pop("TEST_CONTRIBSIM_KEY", None)
            os.unlink(env_path)

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

    @patch("app.gemma.request.urlopen")
    def test_gemini_client_sends_json_request(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}
        ).encode()

        result = GeminiClient(api_key="secret", model="test-model").generate("hello")

        self.assertEqual(result, '{"ok": true}')
        sent_request = urlopen.call_args.args[0]
        sent_payload = json.loads(sent_request.data.decode())
        self.assertIn("key=secret", sent_request.full_url)
        self.assertEqual(sent_payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(sent_payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "minimal")
        self.assertIn("issue_summary", sent_payload["generationConfig"]["responseJsonSchema"]["required"])


if __name__ == "__main__":
    unittest.main()
