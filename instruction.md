# Sealflow policy compiler repair

The `/app/sealflow` package contains a small command-line compiler for `.seal` policy scripts. The current implementation produces unstable and incorrect policy reports. Repair `/app/sealflow/compiler.py` so the compiler follows the rules below.

A Sealflow script contains permit declarations and policy blocks. Permit declarations look like `permit short_name = concrete_rule`. Policy blocks start with `policy name:` and then contain one or more chain lines such as `badge -> zone -> audit`. Blank lines and comments beginning with `#` should be ignored.

The compiler should write `/app/output/policy_report.json` when run from `/app` with:

```bash
python -m sealflow.compiler /app/programs/access_shift.seal --out /app/output/policy_report.json
```

The report must be deterministic. It should preserve the order in which permits and policies first appear in the source file. Each policy's `rules` list should preserve the chain order from the file after permit expansion. Do not alphabetize permit names, policy names, or rule entries.

Permit handling is strict. If a permit is declared more than once with the same concrete rule, keep the first declaration and add one issue string `DUPLICATE_PERMIT:<permit>`. If a permit is declared again with a different concrete rule, keep the first declaration and add one issue string `CONFLICTING_PERMIT:<permit>`. Repeating the same duplicate or conflict later in the file should not create repeated issue strings.

The literal token `STOP` means the policy chain stops at that point. The compiler should add `POLICY_STOP:<policy-name>:<position>` where the position is one-based within the original chain line, and it should ignore that `STOP` token and every later token on the same chain line. Unknown tokens that are not permits, not concrete lowercase rule names, and not `STOP` should add `UNKNOWN_SYMBOL:<token>` and be skipped.

Keep the command-line interface intact. The verifier uses the system-wide Python runtime and does not require project-specific test tooling.

## Required JSON schema

The output file `/app/output/policy_report.json` must be a JSON object with exactly these top-level keys:

```json
{
  "permits": [
    {
      "name": "badge",
      "target": "identify"
    }
  ],
  "policies": [
    {
      "name": "morning",
      "rules": ["identify", "enter", "log"],
      "rule_count": 3
    }
  ],
  "issues": [
    "DUPLICATE_PERMIT:badge"
  ]
}
```

The `permits` value must be an array of objects. Each permit object must contain `name` and `target` string fields. The array order must match the first appearance of each permit declaration in the source file.

The `policies` value must be an array of objects. Each policy object must contain a `name` string, a `rules` array of strings, and a `rule_count` integer equal to the length of `rules`. The array order must match the first appearance of each policy block in the source file.

The `issues` value must be an array of strings. Issue strings must appear at most once each and should be emitted in the order the issue is first encountered while reading the source file.
