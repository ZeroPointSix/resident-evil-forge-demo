#!/usr/bin/env python3
"""Validate model, animation, texture, Blockbench, and evidence contracts."""

import json
import sys

from creature_assets_lib import validate_all


if __name__ == "__main__":
    report = validate_all()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["status"] == "PASS" else 1)
