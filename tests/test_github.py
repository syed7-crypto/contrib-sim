import base64
import json
import unittest
from unittest.mock import patch

from app.github import (
    GitHubCollector,
    build_symbol_index,
    decode_content,
    detect_language,
    limit_content,
    parse_github_urls,
    rank_context_files,
    select_context_files,
)


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

    def test_select_context_files_uses_issue_terms(self):
        entries = [
            {"type": "blob", "path": "src/auth.py"},
            {"type": "blob", "path": "src/parser.py"},
            {"type": "blob", "path": "tests/test_parser.py"},
        ]
        selected = select_context_files(entries, issue_text="Parser validation is failing")
        self.assertEqual(selected[0], "tests/test_parser.py")
        self.assertEqual(selected[1], "src/parser.py")

    def test_exact_class_match_is_ranked_highly(self):
        entries = [{"type": "blob", "path": "src/url_safe.py"}, {"type": "blob", "path": "src/other.py"}]
        symbols = build_symbol_index({"src/url_safe.py": "class URLSafeSerializer:\n    pass", "src/other.py": "class Other:\n    pass"})
        ranked = rank_context_files(entries, issue_text="URLSafeSerializer", symbol_index=symbols)
        self.assertEqual(ranked[0]["path"], "src/url_safe.py")
        self.assertIn("exact symbol match: URLSafeSerializer", ranked[0]["reasons"])

    def test_exact_method_match_is_ranked_highly(self):
        entries = [{"type": "blob", "path": "src/serializer.py"}, {"type": "blob", "path": "src/other.py"}]
        symbols = build_symbol_index({"src/serializer.py": "class Serializer:\n    def loads(self, value):\n        return value", "src/other.py": "def dumps(value):\n    return value"})
        ranked = rank_context_files(entries, issue_text="loads", symbol_index=symbols)
        self.assertEqual(ranked[0]["path"], "src/serializer.py")
        self.assertIn("exact symbol match: loads", ranked[0]["reasons"])

    def test_class_and_method_match(self):
        entries = [{"type": "blob", "path": "src/url_safe.py"}, {"type": "blob", "path": "src/other.py"}]
        symbols = build_symbol_index({"src/url_safe.py": "class URLSafeSerializer:\n    def loads(self, value):\n        return value", "src/other.py": "def loads(value):\n    return value"})
        ranked = rank_context_files(entries, issue_text="URLSafeSerializer.loads", symbol_index=symbols)
        self.assertEqual(ranked[0]["path"], "src/url_safe.py")
        self.assertIn("exact symbol match: URLSafeSerializer", ranked[0]["reasons"])
        self.assertIn("exact symbol match: loads", ranked[0]["reasons"])

    def test_filename_only_match(self):
        entries = [{"type": "blob", "path": "src/parser.py"}, {"type": "blob", "path": "src/auth.py"}]
        ranked = rank_context_files(entries, issue_text="parser", symbol_index={})
        self.assertEqual(ranked[0]["path"], "src/parser.py")

    def test_issue_keyword_match_is_explainable(self):
        entries = [{"type": "blob", "path": "src/parser.py"}, {"type": "blob", "path": "src/auth.py"}]
        ranked = rank_context_files(entries, issue_text="parser validation", symbol_index={})
        self.assertIn("issue keyword match: parser", ranked[0]["reasons"])

    def test_unrelated_file_ranks_lower(self):
        entries = [{"type": "blob", "path": "src/parser.py"}, {"type": "blob", "path": "src/unrelated.py"}]
        ranked = rank_context_files(entries, issue_text="parser", symbol_index={})
        scores = {item["path"]: item["score"] for item in ranked}
        self.assertGreater(scores["src/parser.py"], scores["src/unrelated.py"])

    def test_missing_symbol_does_not_create_evidence_match(self):
        entries = [{"type": "blob", "path": "src/parser.py"}]
        symbols = build_symbol_index({"src/parser.py": "def parse(value):\n    return value"})
        ranked = rank_context_files(entries, issue_text="MissingParser", symbol_index=symbols)
        self.assertFalse(any("symbol match" in reason for reason in ranked[0]["reasons"]))

    def test_itsdangerous_issue_selects_url_safe_module(self):
        entries = [
            {"type": "blob", "path": "src/itsdangerous/url_safe.py"},
            {"type": "blob", "path": "src/itsdangerous/serializer.py"},
            {"type": "blob", "path": "tests/test_itsdangerous/test_url_safe.py"},
            {"type": "blob", "path": "tests/test_itsdangerous/test_signer.py"},
        ]
        contents = {
            "src/itsdangerous/url_safe.py": "class URLSafeSerializer:\n    def loads(self, value):\n        return value",
            "src/itsdangerous/serializer.py": "class Serializer:\n    def loads(self, value):\n        return value",
            "tests/test_itsdangerous/test_url_safe.py": "def test_url_safe():\n    pass",
            "tests/test_itsdangerous/test_signer.py": "def test_signer():\n    pass",
        }
        selected = select_context_files(
            entries,
            max_files=3,
            issue_text="URLSafeSerializer.loads silently ignores max_age",
            symbol_index=build_symbol_index(contents),
        )
        self.assertIn("src/itsdangerous/url_safe.py", selected)

    def test_detect_language(self):
        self.assertEqual(detect_language("src/parser.py"), "Python")
        self.assertEqual(detect_language("README.md"), "Markdown")

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
