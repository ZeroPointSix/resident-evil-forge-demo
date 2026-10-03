#!/usr/bin/env python3
"""Render disclosed offline evidence directly from generated resources."""

import json

from creature_assets_lib import render_all


if __name__ == "__main__":
    print(json.dumps(render_all(), indent=2, ensure_ascii=False))
