"""Tests for code quality tasks module."""
import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from invoke.context import Context

from invoke_tasks.code import (
    _complexity_threshold_to_grade,
    autoformat,
    check,
    ci,
    clean,
    complexity,
    coverage,
    coverage_open,
    coverage_score,
    coverage_xml,
    deadcode,
    docstrings,
    docs,
    docs_serve,
    duplication,
    licenses,
    mypy,
    osv_scan,
    security,
    test as invoke_test,
    ty,
    typecov,
)


def make_ctx(exited: int = 0, stdout: str = "") -> MagicMock:
    """Mock invoke Context whose run() always returns the same result.

    spec=Context ensures isinstance(ctx, Context) passes invoke's guard.
    """
    ctx = MagicMock(spec=Context)
    result = MagicMock()
    result.exited = exited
    result.stdout = stdout
    ctx.run.return_value = result
    return ctx


def make_ctx_multi(*results: tuple[int, str]) -> MagicMock:
    """Mock invoke Context with different results per successive run() call.

    Each element of *results is a (exited, stdout) tuple.
    """
    ctx = MagicMock(spec=Context)
    side = []
    for exited, stdout in results:
        r = MagicMock()
        r.exited = exited
        r.stdout = stdout
        side.append(r)
    ctx.run.side_effect = side
    return ctx


def run_cmds(ctx: MagicMock) -> list[str]:
    """Return every command string passed to ctx.run()."""
    return [c.args[0] for c in ctx.run.call_args_list]


# ─────────────────────────────────────────────────────────────
# _complexity_threshold_to_grade
# ─────────────────────────────────────────────────────────────


class TestComplexityThresholdToGrade:
    @pytest.mark.parametrize(
        "threshold,grade",
        [
            (1, "B"),
            (5, "B"),
            (6, "C"),
            (10, "C"),
            (11, "D"),
            (20, "D"),
            (21, "E"),
            (30, "E"),
            (31, "F"),
            (40, "F"),
            (41, "F"),
            (100, "F"),
        ],
    )
    def test_grade_boundaries(self, threshold: int, grade: str) -> None:
        assert _complexity_threshold_to_grade(threshold) == grade


# ─────────────────────────────────────────────────────────────
# autoformat
# ─────────────────────────────────────────────────────────────


class TestAutoformat:
    def test_runs_black_ruff_format_and_ruff_fix(self) -> None:
        ctx = make_ctx()
        autoformat(ctx)
        cmds = run_cmds(ctx)
        assert any("black" in c for c in cmds)
        assert any("ruff format" in c for c in cmds)
        assert any("ruff check" in c and "--fix" in c for c in cmds)

    def test_passes_path_to_all_commands(self) -> None:
        ctx = make_ctx()
        autoformat(ctx, path="src")
        for cmd in run_cmds(ctx):
            assert "src" in cmd


# ─────────────────────────────────────────────────────────────
# check
# ─────────────────────────────────────────────────────────────


class TestCheck:
    def test_runs_ruff_format_diff_and_ruff_check(self) -> None:
        ctx = make_ctx()
        check(ctx)
        cmds = run_cmds(ctx)
        assert any("ruff format --diff" in c for c in cmds)
        assert any("ruff check" in c and "--diff" not in c for c in cmds)

    def test_passes_path_to_commands(self) -> None:
        ctx = make_ctx()
        check(ctx, path="src")
        for cmd in run_cmds(ctx):
            assert "src" in cmd

    def test_exits_when_format_fails(self) -> None:
        ctx = make_ctx_multi((1, ""), (0, ""))
        with pytest.raises(SystemExit):
            check(ctx)

    def test_exits_when_lint_fails(self) -> None:
        ctx = make_ctx_multi((0, ""), (1, ""))
        with pytest.raises(SystemExit):
            check(ctx)

    def test_succeeds_when_all_pass(self, capsys) -> None:
        ctx = make_ctx(exited=0)
        check(ctx)  # must not raise
        assert "properly formatted" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# mypy
# ─────────────────────────────────────────────────────────────


class TestMypy:
    def test_runs_mypy(self) -> None:
        ctx = make_ctx()
        mypy(ctx)
        assert "mypy" in ctx.run.call_args.args[0]

    def test_passes_path(self) -> None:
        ctx = make_ctx()
        mypy(ctx, path="src/pkg")
        assert "src/pkg" in ctx.run.call_args.args[0]


# ─────────────────────────────────────────────────────────────
# ty
# ─────────────────────────────────────────────────────────────


class TestTy:
    def test_runs_ty_check(self) -> None:
        ctx = make_ctx()
        ty(ctx)
        assert "ty check" in ctx.run.call_args.args[0]

    def test_passes_path(self) -> None:
        ctx = make_ctx()
        ty(ctx, path="src")
        assert "src" in ctx.run.call_args.args[0]


# ─────────────────────────────────────────────────────────────
# test
# ─────────────────────────────────────────────────────────────


class TestTest:
    def test_runs_pytest(self) -> None:
        ctx = make_ctx()
        invoke_test(ctx)
        assert "pytest" in ctx.run.call_args.args[0]

    def test_includes_environment_variable(self) -> None:
        ctx = make_ctx()
        invoke_test(ctx, env="CUSTOM")
        assert "CUSTOM" in ctx.run.call_args.args[0]

    def test_passes_path(self) -> None:
        ctx = make_ctx()
        invoke_test(ctx, path="tests/unit")
        assert "tests/unit" in ctx.run.call_args.args[0]


# ─────────────────────────────────────────────────────────────
# coverage
# ─────────────────────────────────────────────────────────────


class TestCoverage:
    def test_runs_pytest_cov_and_generates_html(self) -> None:
        ctx = make_ctx()
        coverage(ctx)
        cmds = run_cmds(ctx)
        assert any("--cov" in c for c in cmds)
        assert any("coverage html" in c for c in cmds)

    def test_passes_env_to_pytest(self) -> None:
        ctx = make_ctx()
        coverage(ctx, env="STAGING")
        assert any("STAGING" in c for c in run_cmds(ctx))

    def test_passes_path(self) -> None:
        ctx = make_ctx()
        coverage(ctx, path="src/pkg")
        assert any("src/pkg" in c for c in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# coverage_open
# ─────────────────────────────────────────────────────────────


class TestCoverageOpen:
    def _mock_path(self, exists: bool) -> MagicMock:
        mock_instance = MagicMock()
        mock_instance.exists.return_value = exists
        mock_cls = MagicMock()
        mock_cls.return_value.absolute.return_value = mock_instance
        return mock_cls

    def test_opens_browser_when_report_exists(self) -> None:
        with (
            patch("invoke_tasks.code.coverage"),
            patch("invoke_tasks.code.Path", self._mock_path(exists=True)),
            patch("invoke_tasks.code.webbrowser") as mock_browser,
        ):
            coverage_open(make_ctx())
        mock_browser.open.assert_called_once()

    def test_prints_warning_when_report_missing(self, capsys) -> None:
        with (
            patch("invoke_tasks.code.coverage"),
            patch("invoke_tasks.code.Path", self._mock_path(exists=False)),
        ):
            coverage_open(make_ctx())
        assert "not found" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# coverage_xml
# ─────────────────────────────────────────────────────────────


class TestCoverageXml:
    def test_runs_pytest_with_xml_report(self) -> None:
        ctx = make_ctx()
        coverage_xml(ctx)
        assert "--cov-report=xml" in ctx.run.call_args.args[0]

    def test_passes_path(self) -> None:
        ctx = make_ctx()
        coverage_xml(ctx, path="src")
        assert "src" in ctx.run.call_args.args[0]


# ─────────────────────────────────────────────────────────────
# coverage_score
# ─────────────────────────────────────────────────────────────


class TestCoverageScore:
    def test_prints_score_from_stdout(self, capsys) -> None:
        ctx = make_ctx(stdout="85%\n")
        coverage_score(ctx)
        assert "85%" in capsys.readouterr().out

    def test_prints_warning_when_stdout_empty(self, capsys) -> None:
        ctx = make_ctx(stdout="")
        coverage_score(ctx)
        assert "Could not determine" in capsys.readouterr().out

    def test_prints_warning_when_result_is_none(self, capsys) -> None:
        ctx = make_ctx()
        ctx.run.return_value = None
        coverage_score(ctx)
        assert "Could not determine" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# security
# ─────────────────────────────────────────────────────────────


class TestSecurity:
    def test_runs_bandit_and_pip_audit(self) -> None:
        ctx = make_ctx()
        security(ctx)
        cmds = run_cmds(ctx)
        assert any("bandit" in c for c in cmds)
        assert any("pip-audit" in c for c in cmds)

    def test_passes_path_to_bandit(self) -> None:
        ctx = make_ctx()
        security(ctx, path="src")
        cmds = run_cmds(ctx)
        assert any("bandit" in c and "src" in c for c in cmds)

    def test_exits_when_bandit_fails(self) -> None:
        ctx = make_ctx_multi((1, ""), (0, ""))
        with pytest.raises(SystemExit):
            security(ctx)

    def test_exits_when_pip_audit_fails(self) -> None:
        ctx = make_ctx_multi((0, ""), (1, ""))
        with pytest.raises(SystemExit):
            security(ctx)

    def test_succeeds_when_both_pass(self, capsys) -> None:
        ctx = make_ctx(exited=0)
        security(ctx)
        assert "No security issues" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# osv_scan
# ─────────────────────────────────────────────────────────────


class TestOsvScan:
    def test_runs_osv_scanner_with_lockfile(self) -> None:
        ctx = make_ctx()
        osv_scan(ctx)
        cmd = ctx.run.call_args.args[0]
        assert "osv-scanner" in cmd
        assert "uv.lock" in cmd

    def test_exits_when_vulnerabilities_found(self) -> None:
        ctx = make_ctx(exited=1)
        with pytest.raises(SystemExit):
            osv_scan(ctx)

    def test_succeeds_when_no_vulnerabilities(self, capsys) -> None:
        ctx = make_ctx(exited=0)
        osv_scan(ctx)
        assert "No known vulnerabilities" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# complexity
# ─────────────────────────────────────────────────────────────


class TestComplexity:
    def test_exits_when_violations_found(self) -> None:
        ctx = make_ctx(stdout="some_func C (12)")
        with pytest.raises(SystemExit):
            complexity(ctx)

    def test_succeeds_when_no_violations(self, capsys) -> None:
        ctx = make_ctx(stdout="")
        complexity(ctx)
        assert "within complexity threshold" in capsys.readouterr().out

    def test_whitespace_stdout_not_treated_as_violation(self, capsys) -> None:
        ctx = make_ctx(stdout="   \n  ")
        complexity(ctx)
        assert "within complexity threshold" in capsys.readouterr().out

    def test_verbose_runs_extra_radon_commands(self) -> None:
        ctx = make_ctx(stdout="")
        complexity(ctx, verbose=True)
        # 2 verbose calls + 1 violations check
        assert ctx.run.call_count == 3

    def test_non_verbose_runs_single_command(self) -> None:
        ctx = make_ctx(stdout="")
        complexity(ctx, verbose=False)
        assert ctx.run.call_count == 1

    def test_uses_correct_grade_for_threshold(self) -> None:
        ctx = make_ctx(stdout="")
        complexity(ctx, max_complexity=10)
        assert any("--min C" in c for c in run_cmds(ctx))

    def test_passes_path(self) -> None:
        ctx = make_ctx(stdout="")
        complexity(ctx, path="src")
        assert any("src" in c for c in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# deadcode
# ─────────────────────────────────────────────────────────────


class TestDeadcode:
    def test_runs_vulture(self) -> None:
        ctx = make_ctx()
        deadcode(ctx)
        assert "vulture" in ctx.run.call_args.args[0]

    def test_passes_min_confidence(self) -> None:
        ctx = make_ctx()
        deadcode(ctx, min_confidence=90)
        assert "90" in ctx.run.call_args.args[0]

    def test_informational_mode_does_not_exit(self) -> None:
        ctx = make_ctx(exited=1)
        deadcode(ctx, strict=False)  # must not raise

    def test_strict_mode_exits_when_dead_code_found(self) -> None:
        ctx = make_ctx(exited=1)
        with pytest.raises(SystemExit):
            deadcode(ctx, strict=True)

    def test_succeeds_when_no_dead_code(self, capsys) -> None:
        ctx = make_ctx(exited=0)
        deadcode(ctx)
        assert "No dead code detected" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# docstrings
# ─────────────────────────────────────────────────────────────


class TestDocstrings:
    def test_runs_interrogate(self) -> None:
        ctx = make_ctx()
        docstrings(ctx)
        assert "interrogate" in ctx.run.call_args.args[0]

    def test_passes_min_coverage(self) -> None:
        ctx = make_ctx()
        docstrings(ctx, min_coverage=90)
        assert "90" in ctx.run.call_args.args[0]

    def test_informational_mode_does_not_exit(self) -> None:
        ctx = make_ctx(exited=1)
        docstrings(ctx, strict=False)  # must not raise

    def test_strict_mode_exits_below_threshold(self) -> None:
        ctx = make_ctx(exited=1)
        with pytest.raises(SystemExit):
            docstrings(ctx, strict=True)

    def test_succeeds_when_coverage_meets_threshold(self, capsys) -> None:
        ctx = make_ctx(exited=0)
        docstrings(ctx)
        assert "meets threshold" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# typecov
# ─────────────────────────────────────────────────────────────

_TYPECOV_REPORT = "| Total | 20.00% imprecise | 1000 LOC |"


class TestTypecov:
    def test_runs_mypy_with_html_report(self) -> None:
        ctx = make_ctx()
        with patch("builtins.open", side_effect=FileNotFoundError):
            typecov(ctx)
        cmd = ctx.run.call_args.args[0]
        assert "mypy" in cmd
        assert "--html-report" in cmd

    def test_prints_warning_when_report_file_missing(self, capsys) -> None:
        ctx = make_ctx()
        with patch("builtins.open", side_effect=FileNotFoundError):
            typecov(ctx)
        assert "not generated" in capsys.readouterr().out

    def test_parses_coverage_percentage(self, capsys) -> None:
        ctx = make_ctx()
        with patch("builtins.open", mock_open(read_data=_TYPECOV_REPORT)):
            typecov(ctx)
        # 20% imprecise → 80% coverage
        assert "80.00%" in capsys.readouterr().out

    def test_prints_warning_when_pattern_not_found(self, capsys) -> None:
        ctx = make_ctx()
        with patch("builtins.open", mock_open(read_data="no useful content here")):
            typecov(ctx)
        assert "Could not parse" in capsys.readouterr().out

    def test_strict_exits_below_threshold(self) -> None:
        ctx = make_ctx()
        # 90% imprecise → 10% coverage, below default 80% threshold
        report = "| Total | 90.00% imprecise | 1000 LOC |"
        with patch("builtins.open", mock_open(read_data=report)):
            with pytest.raises(SystemExit):
                typecov(ctx, strict=True)

    def test_informational_mode_does_not_exit_below_threshold(self) -> None:
        ctx = make_ctx()
        report = "| Total | 90.00% imprecise | 1000 LOC |"
        with patch("builtins.open", mock_open(read_data=report)):
            typecov(ctx, strict=False)  # must not raise

    def test_opens_browser_when_open_report_true(self) -> None:
        ctx = make_ctx()
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_cls = MagicMock()
        mock_path_cls.return_value.absolute.return_value = mock_path_instance

        with (
            patch("builtins.open", mock_open(read_data=_TYPECOV_REPORT)),
            patch("invoke_tasks.code.Path", mock_path_cls),
            patch("invoke_tasks.code.webbrowser") as mock_browser,
        ):
            typecov(ctx, open_report=True)
        mock_browser.open.assert_called_once()


# ─────────────────────────────────────────────────────────────
# licenses
# ─────────────────────────────────────────────────────────────


class TestLicenses:
    def test_runs_pip_licenses(self) -> None:
        ctx = make_ctx()
        licenses(ctx)
        assert "pip-licenses" in ctx.run.call_args.args[0]

    def test_uses_requested_output_format(self) -> None:
        ctx = make_ctx()
        licenses(ctx, output_format="json")
        assert any("--format=json" in c for c in run_cmds(ctx))

    def test_checks_for_problematic_licenses_when_fail_on_set(self) -> None:
        packages = [{"Name": "bad-pkg", "License": "GPL-3.0"}]
        ctx = make_ctx_multi((0, ""), (0, json.dumps(packages)))
        licenses(ctx, fail_on="GPL")
        assert any("json" in c and "pip-licenses" in c for c in run_cmds(ctx))

    def test_strict_exits_when_problematic_license_found(self) -> None:
        packages = [{"Name": "bad-pkg", "License": "GPL-3.0"}]
        ctx = make_ctx_multi((0, ""), (0, json.dumps(packages)))
        with pytest.raises(SystemExit):
            licenses(ctx, fail_on="GPL", strict=True)

    def test_informational_mode_does_not_exit_on_problematic_license(self) -> None:
        packages = [{"Name": "bad-pkg", "License": "GPL-3.0"}]
        ctx = make_ctx_multi((0, ""), (0, json.dumps(packages)))
        licenses(ctx, fail_on="GPL", strict=False)  # must not raise

    def test_no_exit_when_no_problematic_licenses_found(self, capsys) -> None:
        packages = [{"Name": "mit-pkg", "License": "MIT"}]
        ctx = make_ctx_multi((0, ""), (0, json.dumps(packages)))
        licenses(ctx, fail_on="GPL")
        assert "No problematic licenses" in capsys.readouterr().out

    def test_strict_exits_when_result_non_zero(self) -> None:
        ctx = make_ctx(exited=1)
        with pytest.raises(SystemExit):
            licenses(ctx, strict=True)


# ─────────────────────────────────────────────────────────────
# duplication
# ─────────────────────────────────────────────────────────────


class TestDuplication:
    def test_runs_pylint_duplicate_code_check(self) -> None:
        ctx = make_ctx()
        duplication(ctx)
        cmd = ctx.run.call_args.args[0]
        assert "pylint" in cmd
        assert "duplicate-code" in cmd

    def test_passes_min_lines(self) -> None:
        ctx = make_ctx()
        duplication(ctx, min_lines=10)
        assert "10" in ctx.run.call_args.args[0]

    def test_informational_mode_does_not_exit(self) -> None:
        ctx = make_ctx(exited=1)
        duplication(ctx, strict=False)  # must not raise

    def test_strict_mode_exits_when_duplicates_found(self) -> None:
        ctx = make_ctx(exited=1)
        with pytest.raises(SystemExit):
            duplication(ctx, strict=True)

    def test_succeeds_when_no_duplicates(self, capsys) -> None:
        ctx = make_ctx(exited=0)
        duplication(ctx)
        assert "No code duplication" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# clean
# ─────────────────────────────────────────────────────────────


class TestClean:
    def test_removes_mypy_cache(self) -> None:
        ctx = make_ctx()
        clean(ctx)
        cmds = run_cmds(ctx)
        assert any("mypy_cache" in c or "mypy-coverage" in c for c in cmds)

    def test_removes_pytest_cache(self) -> None:
        ctx = make_ctx()
        clean(ctx)
        assert any("pytest_cache" in c for c in run_cmds(ctx))

    def test_removes_ruff_cache(self) -> None:
        ctx = make_ctx()
        clean(ctx)
        assert any("ruff_cache" in c for c in run_cmds(ctx))

    def test_removes_htmlcov(self) -> None:
        ctx = make_ctx()
        clean(ctx)
        assert any("htmlcov" in c for c in run_cmds(ctx))

    def test_runs_multiple_commands(self) -> None:
        ctx = make_ctx()
        clean(ctx)
        assert ctx.run.call_count > 5


# ─────────────────────────────────────────────────────────────
# docs
# ─────────────────────────────────────────────────────────────


class TestDocs:
    def test_runs_mkdocs_build(self) -> None:
        ctx = make_ctx()
        docs(ctx)
        assert "mkdocs build" in ctx.run.call_args.args[0]

    def test_prints_success_message(self, capsys) -> None:
        ctx = make_ctx()
        docs(ctx)
        assert "Documentation built" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# docs_serve
# ─────────────────────────────────────────────────────────────


class TestDocsServe:
    def test_runs_mkdocs_serve(self) -> None:
        ctx = make_ctx()
        docs_serve(ctx)
        assert "mkdocs serve" in ctx.run.call_args.args[0]


# ─────────────────────────────────────────────────────────────
# ci
# ─────────────────────────────────────────────────────────────


class TestCi:
    def test_calls_all_ci_steps(self) -> None:
        with (
            patch("invoke_tasks.code.autoformat") as mock_autoformat,
            patch("invoke_tasks.code.check") as mock_check,
            patch("invoke_tasks.code.ty") as mock_ty,
            patch("invoke_tasks.code.mypy") as mock_mypy,
            patch("invoke_tasks.code.complexity") as mock_complexity,
            patch("invoke_tasks.code.test") as mock_invoke_test,
        ):
            ci(make_ctx())

        mock_autoformat.assert_called_once()
        mock_check.assert_called_once()
        mock_ty.assert_called_once()
        mock_mypy.assert_called_once()
        mock_complexity.assert_called_once()
        mock_invoke_test.assert_called_once()

    def test_passes_path_to_subtasks(self) -> None:
        with (
            patch("invoke_tasks.code.autoformat") as mock_autoformat,
            patch("invoke_tasks.code.check"),
            patch("invoke_tasks.code.ty"),
            patch("invoke_tasks.code.mypy"),
            patch("invoke_tasks.code.complexity"),
            patch("invoke_tasks.code.test"),
        ):
            ci(make_ctx(), path="src")

        _, kwargs = mock_autoformat.call_args
        assert kwargs.get("path") == "src"

    def test_passes_env_to_test(self) -> None:
        with (
            patch("invoke_tasks.code.autoformat"),
            patch("invoke_tasks.code.check"),
            patch("invoke_tasks.code.ty"),
            patch("invoke_tasks.code.mypy"),
            patch("invoke_tasks.code.complexity"),
            patch("invoke_tasks.code.test") as mock_invoke_test,
        ):
            ci(make_ctx(), env="PROD")

        _, kwargs = mock_invoke_test.call_args
        assert kwargs.get("env") == "PROD"
