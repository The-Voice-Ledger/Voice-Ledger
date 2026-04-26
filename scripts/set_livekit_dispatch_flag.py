#!/usr/bin/env python3
"""Set or unset LIVEKIT_FORCE_EXPLICIT_DISPATCH on Railway Voice-Ledger service."""
import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable", action="store_true", help="Set LIVEKIT_FORCE_EXPLICIT_DISPATCH=true")
    parser.add_argument("--disable", action="store_true", help="Set LIVEKIT_FORCE_EXPLICIT_DISPATCH=false")
    args = parser.parse_args()

    if args.enable == args.disable:
        print("Use exactly one of --enable or --disable")
        return 2

    value = "true" if args.enable else "false"
    cmd = [
        "railway",
        "variables",
        "--service",
        "Voice-Ledger",
        "--set",
        f"LIVEKIT_FORCE_EXPLICIT_DISPATCH={value}",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0:
        if res.stderr.strip():
            print(res.stderr.strip())
        return res.returncode

    print(f"SUCCESS: LIVEKIT_FORCE_EXPLICIT_DISPATCH={value} on Voice-Ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
