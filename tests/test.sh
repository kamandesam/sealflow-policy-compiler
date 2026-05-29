#!/bin/bash
set +e
APP_DIR="${APP_DIR:-/app}"
TESTS_DIR="${TESTS_DIR:-/tests}"
LOGS_DIR="${LOGS_DIR:-/logs/verifier}"
mkdir -p "$LOGS_DIR"
cd "$APP_DIR" || exit 1
python - "$TESTS_DIR/test_outputs.py" <<'PY'
import importlib.util
import sys
import traceback

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("test_outputs", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

passed = 0
failed = 0
for name, func in module.__dict__.items():
    if not name.startswith("test_") or not callable(func):
        continue
    try:
        func()
    except Exception:
        failed += 1
        print(f"FAILED {name}")
        traceback.print_exc()
    else:
        passed += 1
        print(f"PASSED {name}")

if failed:
    print(f"{failed} failed, {passed} passed")
    raise SystemExit(1)
print(f"{passed} passed")
PY
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > "$LOGS_DIR/reward.txt"
else
  echo 0 > "$LOGS_DIR/reward.txt"
fi
exit 0
