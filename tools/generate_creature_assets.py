#!/usr/bin/env python3
"""Generate GeckoLib resources and Blockbench source projects."""

import json

from integrate_approved_models import generate_all


if __name__ == "__main__":
    print(json.dumps(generate_all(), indent=2, ensure_ascii=False))
