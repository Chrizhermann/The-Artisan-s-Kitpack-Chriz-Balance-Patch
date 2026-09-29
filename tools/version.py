"""Check or synchronize the three main TP2 versions without running WeiDU."""

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = (
    "ArtisansKitpack/ArtisansKitpack.TP2",
    "ArtisansKitpack_npc/ArtisansKitpack_npc.TP2",
    "ArtisansKitpack_tweak/ArtisansKitpack_tweak.TP2",
)
VERSION_LINE = re.compile(rb"(?m)^[ \t]*VERSION[ \t]+~([^~\r\n]+)~")
FORK_VERSION = re.compile(
    r"v\d+(?:\.\d+)*[a-z]?(?:-dev\.[0-9a-f]{7,40})?-chriz\.[1-9]\d*"
)


def validate_version(version):
    if not FORK_VERSION.fullmatch(version):
        raise ValueError(
            "Use v<upstream-version>[-dev.<commit>]-chriz.<revision>, "
            "for example v4.81a-dev.85928f9-chriz.1."
        )


def read_installers(root):
    records = []
    for relative in INSTALLERS:
        path = root / relative
        data = path.read_bytes()
        matches = list(VERSION_LINE.finditer(data))
        if len(matches) != 1:
            raise ValueError(f"{relative}: expected exactly one VERSION ~...~ line")
        records.append((path, data, matches[0]))
    return records


def check_version(root, expected=None):
    records = read_installers(root)
    versions = {match[1].decode("ascii") for _, _, match in records}
    if len(versions) != 1:
        raise ValueError("Installer VERSION values disagree: " + ", ".join(sorted(versions)))
    version = versions.pop()
    validate_version(version)
    if expected is not None:
        validate_version(expected)
        if version != expected:
            raise ValueError(f"Expected {expected}; installers report {version}")
    return version


def set_version(root, version):
    validate_version(version)
    # Read and validate every installer before changing any of them. Byte slices
    # preserve line endings and all existing changes outside the VERSION value.
    records = read_installers(root)
    for path, data, match in records:
        updated = data[:match.start(1)] + version.encode("ascii") + data[match.end(1):]
        if updated != data:
            path.write_bytes(updated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Check version agreement (default).")
    mode.add_argument("--set", metavar="VERSION", help="Set all three installer versions.")
    parser.add_argument("--expect", metavar="VERSION", help="Require this exact release/tag identity.")
    args = parser.parse_args()
    if args.set is not None and args.expect is not None:
        parser.error("--expect is a check; it cannot be combined with --set")
    try:
        if args.set is not None:
            set_version(ROOT, args.set)
        version = check_version(ROOT, args.expect)
    except (OSError, ValueError, UnicodeError) as error:
        print(f"Version check failed: {error}", file=sys.stderr)
        return 1
    print(f"All three main installers: {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
