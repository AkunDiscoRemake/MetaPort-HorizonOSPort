#!/usr/bin/env python3
"""Inventory local, operator-declared in-scope artifacts without executing them.

Version provenance is NOT verified by this tool. No extraction or RE is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ALLOWED_VERSIONS = ("v2.4", "v2.7")


def inventory(root, version, provenance):
    if version not in ALLOWED_VERSIONS:
        raise ValueError("Out of scope: only v2.4 and v2.7 are allowed")
    if not provenance.strip():
        raise ValueError("A provenance reference is required")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Artifact root must be a real directory, not a symlink")
    root = root.resolve()
    entries = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"Symlinks are not accepted: {path.relative_to(root)}")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ValueError(f"Non-regular artifact: {path.relative_to(root)}")
            digest = hashlib.sha256()
            # Reject symlink replacement of the leaf between inspection and opening.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("Artifact changed type during inventory")
                size = 0
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns
            ) or size != after.st_size:
                raise ValueError("Artifact changed during inventory; use a stable copy")
            entries.append({"path": path.relative_to(root).as_posix(),
                            "size_bytes": size, "sha256": digest.hexdigest()})
    if not entries:
        raise ValueError("Artifact directory is empty")
    return {"schema_version": 1, "declared_version": version,
            "version_verification": "UNVERIFIED",
            "provenance_reference": provenance,
            "port_status": "NOT PORTED YET",
            "files": sorted(entries, key=lambda entry: entry["path"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, choices=ALLOWED_VERSIONS)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--provenance", required=True,
                        help="Reference to local acquisition/build evidence; not a credential")
    args = parser.parse_args()
    try:
        report = inventory(args.artifacts, args.version, args.provenance)
    except (ValueError, OSError) as exc:
        print(f"Inventory refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
