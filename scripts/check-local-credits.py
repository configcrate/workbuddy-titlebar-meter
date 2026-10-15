"""Opt-in smoke check: print success/schema only, never account data or helper logs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import window_anchor
from meter_core import normalize_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-official-request", action="store_true", required=True)
    parser.parse_args()
    host = window_anchor.WindowFinder().find()
    if not host:
        raise SystemExit("Open and sign in to WorkBuddy first.")
    result = subprocess.run([host.path, str(ROOT / "wb_credits_helper.cjs"), "--variant", "auto"],
                            env=dict(os.environ, ELECTRON_RUN_AS_NODE="1", ELECTRON_NO_ATTACH_CONSOLE="1"),
                            capture_output=True, timeout=45, creationflags=0x08000000)
    payload = None
    for line in reversed(result.stdout.decode("utf-8", errors="replace").splitlines()):
        start = line.find('{"ok"')
        if start >= 0:
            try:
                payload = json.loads(line[start:])
                break
            except ValueError:
                pass
    private = {"uid", "nickname", "accessToken", "refreshToken", "tokenExpiresAt"}
    valid = normalize_snapshot(payload) is not None
    clean = isinstance(payload, dict) and not private.intersection(payload)
    print(json.dumps({"ok": valid, "privateFieldsAbsent": clean,
                      "fields": sorted(payload) if isinstance(payload, dict) else []}))
    if not valid or not clean:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
