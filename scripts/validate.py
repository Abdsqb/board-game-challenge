"""Run correctness checks, syntax checks, and isolated bundle smoke tests."""

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                           cwd=ROOT, capture_output=True, text=True, timeout=180)
    output = tests.stdout + tests.stderr
    print(output, end="")
    match = re.search(r"Ran (\d+) tests", output)
    syntax_files = sorted((ROOT / "agents").glob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
    for path in syntax_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))
    digest = hashlib.sha256()
    for path in sorted((ROOT / "agents").glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "runtime_python": platform.python_version(),
              "test_count": int(match.group(1)) if match else None, "tests_passed": tests.returncode == 0,
              "python_3_11_syntax_files": len(syntax_files), "source_sha256": digest.hexdigest(),
              "note": "Executed on the recorded Python runtime; Python 3.11 syntax compatibility is checked, not a 3.11 runtime test.",
              "test_output": output}
    (ROOT / "reports" / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if tests.returncode:
        raise SystemExit(tests.returncode)
    bundles = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_bundles.py")], cwd=ROOT)
    raise SystemExit(bundles.returncode)


if __name__ == "__main__":
    main()
