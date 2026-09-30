#!/usr/bin/env python3
"""Read-only, opt-in ADB preflight. Does not install, root, flash or unlock.

Requires an already authorized USB debugging connection. Reports only selected
properties/features, not full dumps, serial numbers, accounts or application lists.
"""
import argparse
import json
import subprocess
import sys

PROPERTIES = (
    "ro.product.manufacturer", "ro.product.model", "ro.product.device",
    "ro.build.version.release", "ro.build.version.sdk", "ro.product.cpu.abilist",
    "ro.opengles.version", "ro.boot.verifiedbootstate", "ro.boot.flash.locked",
)


def collect(serial=None):
    adb = ["adb"] + (["-s", serial] if serial else [])

    def query(arguments):
        result = subprocess.run(adb + ["shell"] + arguments, capture_output=True,
                                text=True, timeout=15, check=False)
        if result.returncode:
            # Avoid echoing arbitrary device output/identifiers into reports.
            raise RuntimeError("ADB query failed; verify USB authorization and device selection")
        return result.stdout.strip()

    properties = {key: query(["getprop", key]) or None for key in PROPERTIES}
    features = query(["pm", "list", "features"])
    prefixes = ("android.hardware.camera", "android.hardware.sensor",
                "android.hardware.vulkan", "android.hardware.opengles",
                "android.hardware.vr", "android.hardware.camera.ar")
    selected = sorted(line.removeprefix("feature:") for line in features.splitlines()
                      if line.startswith("feature:" + prefixes[0]) or
                      any(line.startswith("feature:" + p) for p in prefixes[1:]))
    return {"schema_version": 1, "source": "adb_read_only_queries",
            "properties": properties, "declared_features": selected,
            "arcore_runtime_availability": "NOT_TESTED",
            "apk_access_to_sensors_camera_gpu": "NOT_TESTED",
            "thermal_and_frame_timing": "NOT_TESTED",
            "port_status": "NOT PORTED YET"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="Select one authorized device; not included in report")
    args = parser.parse_args()
    try:
        report = collect(args.serial)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print("Preflight failed: " + (str(exc) if isinstance(exc, RuntimeError)
                                      else type(exc).__name__), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
