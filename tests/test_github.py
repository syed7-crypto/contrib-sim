import base64
import json
import unittest
from unittest.mock import patch

from app.github import GitHubCollector, decode_content, limit_content, parse_github_urls, select_context_files


class GitHubCollectorTests(unittest.TestCase):
    def test_parse_matching_repository_and_issue_urls(self):
        target = parse_github_urls(
            "https://github.com/example/project",
            "https://github.com/example/project/issues/42",
        )
        self.assertEqual((target.owner, target.repository, target.issue_number), ("example", "project", 42))

    def test_reject_mismatched_repository(self):
        with self.assertRaises(ValueError):
            parse_github_urls(
                "https://github.com/example/project",
                "https://github.com/example/other/issues/42",
            )

    def test_select_context_files_prioritizes_evidence(self):
        entries = [
            {"type": "blob", "path": "src/parser.py"},
            {"type": "blob", "path": "README.md"},
            {"type": "blob", "path": "tests/test_parser.py"},
            {"type": "blob", "path": "node_modules/pkg/index.js"},
        ]
        self.assertEqual(
            select_context_files(entries),
            ["README.md", "tests/test_parser.py", "src/parser.py"],
        )

    def test_decode_content(self):
        encoded = base64.b64encode("hello".encode()).decode()
        self.assertEqual(decode_content({"content": encoded}), "hello")

    def test_limit_content(self):
        self.assertEqual(limit_content("abcdef", 3), "abc\n[File content truncated by ContribSim]")

    @patch("app.github.request.urlopen")
    def test_collect_uses_repository_issue_tree_and_file_endpoints(self, urlopen):
        responses = [
            {"full_name": "example/project", "description": "Demo", "default_branch": "main"},
            {"title": "Fix parser", "state": "open", "body": "Handle empty input."},
            {"tree": [{"type": "blob", "path": "README.md"}, {"type": "blob", "path": "src/parser.py"}]},
            {"content": base64.b64encode(b"# Demo").decode()},
            {"content": base64.b64encode(b"def parse(value):\n    return value").decode()},
        ]

        class FakeResponse:
            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(self.value).encode()

        urlopen.side_effect = [FakeResponse(value) for value in responses]
        target = parse_github_urls(
            "https://github.com/example/project",
            "https://github.com/example/project/issues/7",
        )

        context, issue = GitHubCollector(api_url="https://api.test").collect(target)

        self.assertIn("example/project", context)
        self.assertIn("src/parser.py", context)
        self.assertIn("Fix parser", issue)
        self.assertEqual(urlopen.call_count, 5)


if __name__ == "__main__":
    unittest.main()
