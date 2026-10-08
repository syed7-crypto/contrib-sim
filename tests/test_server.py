import json
import unittest
from unittest.mock import patch

import server


class ServerTests(unittest.TestCase):
    @patch.dict("os.environ", {"CONTRIBSIM_OFFLINE": "1"}, clear=False)
    @patch("server.analyze_context")
    def test_offline_request_uses_existing_pipeline_and_contract(self, analyze):
        analyze.return_value = {"contributor_plan": {}, "grounding": {}, "review": {}}
        result = server.analyze_request({"repository_url": "https://github.com/o/r", "issue_url": "https://github.com/o/r/issues/1"})
        self.assertEqual(set(result), {"contributor_plan", "grounding", "review"})
        analyze.assert_called_once()
        self.assertTrue(analyze.call_args.kwargs["offline"])

    def test_request_requires_both_urls(self):
        with self.assertRaisesRegex(ValueError, "repository_url and issue_url"):
            server.analyze_request({"repository_url": "https://github.com/o/r"})

    @patch("server.GitHubCollector.collect_with_metadata")
    @patch("server.analyze_context")
    def test_online_request_collects_then_analyzes(self, analyze, collect):
        collect.return_value = ("context", "issue", {})
        analyze.return_value = {"contributor_plan": {}, "grounding": {}, "review": {}}
        with patch.dict("os.environ", {"CONTRIBSIM_OFFLINE": "0"}, clear=False):
            result = server.analyze_request({"repository_url": "https://github.com/o/r", "issue_url": "https://github.com/o/r/issues/1"})
        self.assertEqual(set(result), {"contributor_plan", "grounding", "review"})
        collect.assert_called_once()
        analyze.assert_called_once_with("context", "issue", "gemini", model=None, ollama_url="http://localhost:11434", offline=False)


if __name__ == "__main__":
    unittest.main()
