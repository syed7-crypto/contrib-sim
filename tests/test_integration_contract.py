import inspect
import unittest

from app.gemma import GeminiClient, OllamaClient
from app.main import DEFAULT_CONTEXT, DEFAULT_ISSUE, analyze_context


class IntegrationContractTests(unittest.TestCase):
    def test_output_has_stable_top_level_contract(self):
        output = analyze_context(DEFAULT_CONTEXT, DEFAULT_ISSUE, "gemini", offline=True)
        self.assertEqual(set(output), {"contributor_plan", "grounding", "review"})
        self.assertIn("issue_understanding", output["contributor_plan"])
        self.assertIn("relevant_files", output["contributor_plan"])
        self.assertIn("overall_status", output["review"])
        self.assertIn("status", output["grounding"])

    def test_gemini_and_ollama_share_generate_interface(self):
        self.assertEqual(inspect.signature(GeminiClient.generate), inspect.signature(OllamaClient.generate))
        self.assertEqual(list(inspect.signature(GeminiClient.generate).parameters), ["self", "prompt"])


if __name__ == "__main__":
    unittest.main()
