"""Build standalone Python zip applications and smoke-test them outside the source tree."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
GAMES = ("connect4", "clue", "secret-dictator")


def write_member(archive, name, content):
    # Stable metadata makes identical input sources produce identical bundles.
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, content)


def main():
    OUTPUT.mkdir(exist_ok=True)
    source_digest = hashlib.sha256()
    for path in sorted((ROOT / "agents").glob("*.py")):
        source_digest.update(path.name.encode())
        source_digest.update(path.read_bytes())
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "python_required": ">=3.11",
                "protocol": "local-json-lines-v1", "challenge_compatibility_verified": False,
                "submitted": False, "source_sha256": source_digest.hexdigest(), "artifacts": []}
    for game in GAMES:
        destination = OUTPUT / f"{game}-agent.pyz"
        entrypoint = ("import sys\n"
                      f"sys.argv[1:1] = ['--game', {game!r}, '--action-only']\n"
                      "from agents.__main__ import main\nmain()\n")
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
            write_member(archive, "__main__.py", entrypoint)
            for path in sorted((ROOT / "agents").glob("*.py")):
                write_member(archive, "agents/" + path.name, path.read_bytes())
        example = (ROOT / "examples" / f"{game}.jsonl").read_text(encoding="utf-8")
        isolated = OUTPUT / ".smoke"
        isolated.mkdir(exist_ok=True)
        result = subprocess.run([sys.executable, "-I", str(destination)], cwd=isolated,
                                input=example, capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or result.stderr:
            raise RuntimeError(f"isolated {game} bundle failed: {result.stderr}")
        action = json.loads(result.stdout)
        if "type" not in action or "error" in action or "diagnostics" in action:
            raise RuntimeError(f"invalid {game} bundle output: {action}")
        if game == "connect4" and action != {"type": "drop", "column": 0}:
            raise RuntimeError("Connect 4 packaged tactical check failed")
        if game == "clue" and (action["type"] != "suggest" or action.get("room") != "study"):
            raise RuntimeError("Clue packaged legality check failed")
        if game == "secret-dictator" and action != {"type": "nominate", "target": 3}:
            raise RuntimeError("Secret Dictator packaged win-condition check failed")
        manifest["artifacts"].append({"file": destination.name, "bytes": destination.stat().st_size,
                                      "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                                      "isolated_smoke_test": "passed", "example_action": action})
        print(f"Built and verified {destination.name}")
    source = OUTPUT / "board-game-agents-source.zip"
    roots = ("agents", "tests", "scripts", "examples", "prompts", "reports")
    allowed = {".py", ".json", ".jsonl", ".md", ".txt"}
    files = [path for root in roots if (ROOT / root).exists()
             for path in (ROOT / root).rglob("*") if path.is_file() and path.suffix in allowed and "__pycache__" not in path.parts]
    files += [p for p in ROOT.iterdir() if p.is_file() and (p.suffix in (".md", ".toml") or p.name == ".gitignore")]
    with ZipFile(source, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            write_member(archive, "board-game-challenge/" + path.relative_to(ROOT).as_posix(), path.read_bytes())
    manifest["artifacts"].append({"file": source.name, "bytes": source.stat().st_size,
                                  "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "SHA256SUMS.txt").write_text("".join(f"{a['sha256']}  {a['file']}\n" for a in manifest["artifacts"]), encoding="utf-8")
    print(f"Source archive and checksums saved in {OUTPUT}")


if __name__ == "__main__":
    main()
