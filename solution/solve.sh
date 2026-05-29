#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/sealflow/compiler.py" <<'PY'
import argparse
import json
from pathlib import Path


def _clean(line):
    return line.split("#", 1)[0].strip()


def _add_issue(issues, seen, issue):
    if issue not in seen:
        issues.append(issue)
        seen.add(issue)


def compile_text(text):
    permits = {}
    permit_order = []
    policies = []
    policy_lookup = {}
    issues = []
    seen_issues = set()
    current_policy = None

    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue

        if line.startswith("permit "):
            body = line[len("permit "):]
            if "=" not in body:
                continue
            left, right = body.split("=", 1)
            name = left.strip()
            target = right.strip()
            if name in permits:
                if permits[name] == target:
                    _add_issue(issues, seen_issues, f"DUPLICATE_PERMIT:{name}")
                else:
                    _add_issue(issues, seen_issues, f"CONFLICTING_PERMIT:{name}")
                continue
            permits[name] = target
            permit_order.append(name)
            continue

        if line.startswith("policy ") and line.endswith(":"):
            name = line[len("policy "):-1].strip()
            policy = {"name": name, "rules": []}
            policies.append(policy)
            policy_lookup[name] = policy
            current_policy = name
            continue

        if current_policy and "->" in line:
            policy = policy_lookup[current_policy]
            for position, token in enumerate((part.strip() for part in line.split("->")), start=1):
                if token == "STOP":
                    _add_issue(issues, seen_issues, f"POLICY_STOP:{current_policy}:{position}")
                    break
                if token in permits:
                    policy["rules"].append(permits[token])
                elif token.islower():
                    policy["rules"].append(token)
                else:
                    _add_issue(issues, seen_issues, f"UNKNOWN_SYMBOL:{token}")

    for policy in policies:
        policy["rule_count"] = len(policy["rules"])

    return {
        "permits": [{"name": name, "target": permits[name]} for name in permit_order],
        "policies": policies,
        "issues": issues,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--out", default="/app/output/policy_report.json")
    args = parser.parse_args(argv)

    report = compile_text(Path(args.source).read_text())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
PY
