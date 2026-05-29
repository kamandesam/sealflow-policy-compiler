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


def _expand_permit(token, permits):
    seen = set()
    current = token
    while current in permits:
        if current in seen:
            return None
        seen.add(current)
        current = permits[current]
    return current


def _parse_file(path, permits, permit_order, policies, policy_lookup, issues, seen_issues, included, stack):
    path = Path(path).resolve()
    if path in stack:
        _add_issue(issues, seen_issues, f"INCLUDE_CYCLE:{path.name}")
        return
    if path in included:
        _add_issue(issues, seen_issues, f"DUPLICATE_INCLUDE:{path.name}")
        return

    included.add(path)
    stack.append(path)
    current_policy = None

    for raw in path.read_text().splitlines():
        line = _clean(raw)
        if not line:
            continue

        if line.startswith("include "):
            include_text = line[len("include "):].strip()
            if include_text.startswith('"') and include_text.endswith('"'):
                include_name = include_text[1:-1]
                _parse_file(path.parent / include_name, permits, permit_order, policies, policy_lookup, issues, seen_issues, included, stack)
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
            header = line[len("policy "):-1].strip()
            parent = None
            if " extends " in header:
                name, parent = header.split(" extends ", 1)
                name = name.strip()
                parent = parent.strip()
            else:
                name = header
            policy = {"name": name, "rules": [], "_parent": parent}
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
                    expanded = _expand_permit(token, permits)
                    if expanded is None:
                        _add_issue(issues, seen_issues, f"PERMIT_CYCLE:{token}")
                    elif expanded.islower():
                        policy["rules"].append(expanded)
                    else:
                        _add_issue(issues, seen_issues, f"UNKNOWN_SYMBOL:{expanded}")
                elif token.islower():
                    policy["rules"].append(token)
                else:
                    _add_issue(issues, seen_issues, f"UNKNOWN_SYMBOL:{token}")

    stack.pop()


def _resolve_policy_rules(name, policy_lookup, issues, seen_issues, stack=None):
    if stack is None:
        stack = []
    if name not in policy_lookup:
        return []
    policy = policy_lookup[name]
    parent = policy.get("_parent")
    own = policy["rules"]

    if not parent:
        return list(own)

    if name in stack:
        _add_issue(issues, seen_issues, f"POLICY_CYCLE:{name}")
        return list(own)

    if parent not in policy_lookup:
        _add_issue(issues, seen_issues, f"UNKNOWN_PARENT:{name}:{parent}")
        return list(own)

    if parent in stack:
        _add_issue(issues, seen_issues, f"POLICY_CYCLE:{name}")
        return list(own)

    inherited = _resolve_policy_rules(parent, policy_lookup, issues, seen_issues, stack + [name])
    return inherited + list(own)


def compile_path(source):
    permits = {}
    permit_order = []
    policies = []
    policy_lookup = {}
    issues = []
    seen_issues = set()
    included = set()

    _parse_file(source, permits, permit_order, policies, policy_lookup, issues, seen_issues, included, [])

    output_policies = []
    for policy in policies:
        name = policy["name"]
        rules = _resolve_policy_rules(name, policy_lookup, issues, seen_issues)
        output_policies.append({"name": name, "rules": rules, "rule_count": len(rules)})

    return {
        "permits": [{"name": name, "target": permits[name]} for name in permit_order],
        "policies": output_policies,
        "issues": issues,
    }


def compile_text(text):
    raise RuntimeError("compile_text is no longer used; call compile_path")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--out", default="/app/output/policy_report.json")
    args = parser.parse_args(argv)

    report = compile_path(args.source)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
PY
