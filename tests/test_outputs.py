import json
import os
import subprocess
from pathlib import Path


APP = Path(os.environ.get("APP_DIR", "/app"))
REPORT = APP / "output" / "policy_report.json"


def run_compiler():
    REPORT.unlink(missing_ok=True)
    source = (
        "/app/programs/access_shift.seal"
        if APP == Path("/app")
        else str(APP / "programs" / "access_shift.seal")
    )
    result = subprocess.run(
        ["python", "-m", "sealflow.compiler", source, "--out", str(REPORT)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert REPORT.exists()
    return json.loads(REPORT.read_text())


def policy_by_name(report, name):
    return next(policy for policy in report["policies"] if policy["name"] == name)


def test_report_file_is_json_object():
    assert isinstance(run_compiler(), dict)


def test_report_has_required_top_level_keys():
    assert set(run_compiler()) == {"permits", "policies", "issues"}


def test_morning_policy_exists():
    assert policy_by_name(run_compiler(), "morning")["name"] == "morning"


def test_morning_expands_simple_permits():
    assert policy_by_name(run_compiler(), "morning")["rules"] == ["identify", "enter", "log"]


def test_permit_order_preserves_first_appearance_across_includes():
    report = run_compiler()
    assert [item["name"] for item in report["permits"]] == [
        "badge",
        "zone",
        "audit",
        "review",
        "lock",
        "visitor",
        "escort",
        "vault",
        "cyclic_shared",
        "loop_a",
        "loop_b",
    ]


def test_duplicate_and_conflicting_permit_issues_are_exact():
    issues = run_compiler()["issues"]
    assert issues.count("DUPLICATE_PERMIT:badge") == 1
    assert issues.count("DUPLICATE_PERMIT:audit") == 1
    assert "CONFLICTING_PERMIT:badge" in issues


def test_policy_order_preserves_include_point_order():
    report = run_compiler()
    assert [policy["name"] for policy in report["policies"]] == [
        "base",
        "inherited",
        "morning",
        "night",
        "exception",
        "relay_line",
        "cyclic",
        "after_hours",
        "unknown_child",
        "trace",
    ]


def test_stop_token_stops_night_policy():
    night = policy_by_name(run_compiler(), "night")
    assert night["rules"] == ["inspect"]
    assert night["rule_count"] == 1


def test_stop_issue_uses_policy_and_position():
    assert "POLICY_STOP:night:2" in run_compiler()["issues"]


def test_unknown_symbol_issue_string_and_skip_behavior():
    exception = policy_by_name(run_compiler(), "exception")
    assert exception["rules"] == ["identify", "secure", "log"]
    assert "UNKNOWN_SYMBOL:GATE_9" in run_compiler()["issues"]


def test_transitive_permit_expansion_from_include():
    relay_line = policy_by_name(run_compiler(), "relay_line")
    assert relay_line["rules"] == ["identify", "log"]
    assert relay_line["rule_count"] == 2


def test_permit_cycle_skips_original_token():
    cyclic = policy_by_name(run_compiler(), "cyclic")
    assert cyclic["rules"] == ["enter"]
    assert cyclic["rule_count"] == 1
    assert "PERMIT_CYCLE:loop_a" in run_compiler()["issues"]


def test_duplicate_include_and_include_cycle_issues():
    issues = run_compiler()["issues"]
    assert "DUPLICATE_INCLUDE:shared.seal" in issues
    assert "INCLUDE_CYCLE:cycle.seal" in issues


def test_policy_inheritance_prepends_parent_rules():
    after_hours = policy_by_name(run_compiler(), "after_hours")
    assert after_hours["rules"] == ["identify", "log", "secure", "log"]
    assert after_hours["rule_count"] == 4


def test_unknown_parent_keeps_child_rules_and_reports_issue():
    report = run_compiler()
    child = policy_by_name(report, "unknown_child")
    assert child["rules"] == ["identify", "log"]
    assert "UNKNOWN_PARENT:unknown_child:missing_parent" in report["issues"]


def test_json_schema_for_every_policy_and_permit():
    report = run_compiler()
    assert all(set(item) == {"name", "target"} for item in report["permits"])
    assert all(set(item) == {"name", "rules", "rule_count"} for item in report["policies"])
    assert all(policy["rule_count"] == len(policy["rules"]) for policy in report["policies"])

def test_duplicate_include_is_reported_once_even_through_deep_chain():
    issues = run_compiler()["issues"]

    assert issues.count("DUPLICATE_INCLUDE:shared.seal") == 1
    assert "INCLUDE_CYCLE:cycle.seal" in issues

