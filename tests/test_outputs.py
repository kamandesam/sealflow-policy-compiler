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
        [
            "python",
            "-m",
            "sealflow.compiler",
            source,
            "--out",
            str(REPORT),
        ],
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
    report = run_compiler()
    assert isinstance(report, dict)


def test_report_has_required_top_level_keys():
    report = run_compiler()
    assert set(report) == {"permits", "policies", "issues"}


def test_morning_policy_exists():
    report = run_compiler()
    assert policy_by_name(report, "morning")["name"] == "morning"


def test_morning_expands_simple_permits():
    report = run_compiler()
    assert policy_by_name(report, "morning")["rules"] == ["identify", "enter", "log"]


def test_permit_order_preserves_first_appearance():
    report = run_compiler()
    assert [item["name"] for item in report["permits"]] == [
        "badge",
        "zone",
        "audit",
        "review",
        "lock",
    ]


def test_duplicate_permit_issue_is_exact_and_deduplicated():
    report = run_compiler()
    assert report["issues"].count("DUPLICATE_PERMIT:badge") == 1
    assert report["issues"].count("DUPLICATE_PERMIT:audit") == 1


def test_conflicting_permit_keeps_first_target():
    report = run_compiler()
    badge = next(item for item in report["permits"] if item["name"] == "badge")
    assert badge["target"] == "identify"
    assert "CONFLICTING_PERMIT:badge" in report["issues"]


def test_policy_order_preserves_source_order():
    report = run_compiler()
    assert [policy["name"] for policy in report["policies"]] == [
        "morning",
        "night",
        "exception",
        "trace",
    ]


def test_stop_token_stops_night_policy():
    report = run_compiler()
    night = policy_by_name(report, "night")
    assert night["rules"] == ["inspect"]
    assert night["rule_count"] == 1


def test_stop_issue_uses_policy_and_position():
    report = run_compiler()
    assert "POLICY_STOP:night:2" in report["issues"]


def test_unknown_symbol_issue_string_and_skip_behavior():
    report = run_compiler()
    exception = policy_by_name(report, "exception")
    assert exception["rules"] == ["identify", "secure", "log"]
    assert "UNKNOWN_SYMBOL:GATE_9" in report["issues"]
