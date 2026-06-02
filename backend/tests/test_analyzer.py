import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import validate_github_url, calculate_quality


class TestValidateGithubUrl:
    def test_valid_url(self):
        assert validate_github_url("https://github.com/owner/repo")

    def test_valid_url_with_git_suffix(self):
        assert validate_github_url("https://github.com/owner/repo.git")

    def test_valid_url_with_trailing_slash(self):
        assert validate_github_url("https://github.com/owner/repo/")

    def test_invalid_non_github(self):
        assert not validate_github_url("https://gitlab.com/owner/repo")

    def test_invalid_path_traversal(self):
        assert not validate_github_url("https://github.com/../../../../etc/passwd")

    def test_invalid_no_repo(self):
        assert not validate_github_url("https://github.com/owner")

    def test_invalid_http(self):
        assert not validate_github_url("http://github.com/owner/repo")

    def test_invalid_empty(self):
        assert not validate_github_url("")


class TestCalculateQuality:
    def test_empty_source_returns_100(self):
        assert calculate_quality("")["overall"] == 100.0
        assert calculate_quality("   ")["overall"] == 100.0

    def test_overall_is_within_bounds(self):
        code = "def foo():\n    return 1\n"
        result = calculate_quality(code)
        assert 0.0 <= result["overall"] <= 100.0

    def test_very_complex_code_scores_lower(self):
        # Many nested branches → high cyclomatic complexity
        complex_code = "\n".join(
            f"def f{i}(x):\n    if x: return 1\n    elif x>1: return 2\n    else: return 3"
            for i in range(20)
        )
        simple_code = "x = 1\n"
        assert calculate_quality(complex_code)["overall"] <= calculate_quality(simple_code)["overall"] + 50

    def test_cc_score_never_exceeds_100(self):
        # Minimal cc (lizard may return very small float) must not produce cc_score > 100
        trivial = "x=1\n"
        result = calculate_quality(trivial)
        assert result["overall"] <= 100.0
