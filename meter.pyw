#!/usr/bin/env python3
"""Compatibility entry point for existing shortcuts and startup entries."""
import os
import sys
import time
import traceback


def launch():
    directory = os.path.dirname(os.path.abspath(__file__))
    # Capture failures before titlebar_meter.main (including tkinter/import errors).
    # Login can precede desktop/runtime readiness. Retry only login launches,
    # for at most two minutes; manual launches still fail promptly.
    attempts = 13 if "--autostart" in sys.argv else 1
    for attempt in range(attempts):
        try:
            os.chdir(directory)
            from titlebar_meter import main
            main()
            return 0
        except Exception:
            try:
                with open(os.path.join(directory, "meter_error.log"), "w", encoding="utf-8") as stream:
                    stream.write(traceback.format_exc()[-8192:])
            except OSError:
                pass
            if attempt + 1 == attempts:
                return 1
            time.sleep(10)

if __name__ == "__main__":
    sys.exit(launch())
