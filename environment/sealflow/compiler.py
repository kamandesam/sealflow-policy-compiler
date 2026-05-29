import argparse
import json
from pathlib import Path


def _clean(line):
    return line.split("#", 1)[0].strip()


def compile_text(text):
    permits = {}
    policies = {}
    issues = []
    current_policy = None

    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue

        if line.startswith("permit "):
            left, right = line[len("permit "):].split("=", 1)
            name = left.strip()
            target = right.strip()
            permits[name] = target
            continue

        if line.startswith("policy ") and line.endswith(":"):
            current_policy = line[len("policy "):-1].strip()
            policies[current_policy] = []
            continue

        if current_policy and "->" in line:
            for token in (part.strip() for part in line.split("->")):
                if token in permits:
                    policies[current_policy].append(permits[token])
                elif token.islower():
                    policies[current_policy].append(token)
                else:
                    issues.append(f"UNKNOWN:{token}")

    return {
        "permits": [{"name": name, "target": permits[name]} for name in sorted(permits)],
        "policies": [
            {"name": name, "rules": policies[name], "rule_count": len(policies[name])}
            for name in sorted(policies)
        ],
        "issues": sorted(set(issues)),
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
