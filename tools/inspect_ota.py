#!/usr/bin/env python3
"""Read bounded OTA packaging metadata only; never extract or execute firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED_SHA256 = "beea2e092f6239ca21af98466d9b130c22b9ab8822f411b00baf74ebb866858e"
METADATA_FILES = ("META-INF/com/android/metadata", "payload_properties.txt")
LIMIT = 1024 * 1024


def inspect(path, expected=EXPECTED_SHA256, include_manifest=False):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while block := stream.read(LIMIT):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("SHA-256 mismatch; inspection refused")
    report = {"sha256": digest.hexdigest(), "catalog_hash_match": True,
              "authenticity": "UNVERIFIED", "stable_channel": "UNVERIFIED",
              "authorized_version": "UNVERIFIED", "full_image": "UNVERIFIED",
              "port_status": "NOT PORTED YET", "metadata": {}}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entry names; inspection refused")
        report["zip_entry_count"] = len(entries)
        report["packaging_entries"] = {
            name: {"size_bytes": archive.getinfo(name).file_size,
                   "compressed_bytes": archive.getinfo(name).compress_size}
            for name in (*METADATA_FILES, "payload.bin", "META-INF/com/android/otacert")
            if name in names
        }
        for name in METADATA_FILES:
            if name not in names:
                continue
            info = archive.getinfo(name)
            if info.file_size > LIMIT:
                raise ValueError("Metadata exceeds size limit")
            with archive.open(info) as stream:
                raw = stream.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("Metadata exceeds size limit")
            text = raw.decode("utf-8", errors="strict")
            fields = {}
            for line in text.splitlines():
                if not line.strip():
                    continue
                if "=" not in line:
                    raise ValueError("Unrecognized metadata syntax")
                key, value = line.split("=", 1)
                if key in fields:
                    raise ValueError("Duplicate metadata key")
                fields[key] = value
            report["metadata"][name] = fields
        if include_manifest:
            from tools.payload_manifest import inspect_payload
            info = archive.getinfo("payload.bin")
            with archive.open(info) as stream:
                report["payload_manifest"] = inspect_payload(
                    stream, info.file_size, report["metadata"]["payload_properties.txt"])
        ota = report["metadata"].get(METADATA_FILES[0], {})
        report["incremental_base_declared"] = any(
            ota.get(key) for key in ("pre-build", "pre-build-incremental"))
        report["notes"] = [
            "Absence of a pre-build requirement does not prove a full image.",
            "Build fingerprints and release-keys do not alone prove a stable channel.",
            "No partition extraction, disassembly or firmware execution performed."
        ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", action="store_true", help="Inspect bounded AOSP packaging manifest")
    args = parser.parse_args()
    report = inspect(args.zip, include_manifest=args.manifest)
    serialized = json.dumps(report, indent=2, ensure_ascii=True)
    args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
