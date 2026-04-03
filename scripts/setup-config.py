#!/usr/bin/env python3
"""Bootstrap user config directory from repo defaults.

Usage:
    python scripts/setup-config.py

This copies default configs from the repo's configs/ directory into the
user-level config directory (~/.config/sea-qwens/ on Linux).

Safe to run multiple times — existing configs are never overwritten.
"""

import sys
import os

# Ensure the project root is on the path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from shared.config import bootstrap_configs, _get_config_dir


def main():
    config_dir = _get_config_dir()
    print(f"User config directory: {config_dir}")

    if config_dir.exists():
        print(f"Config directory already exists: {config_dir}")
    else:
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created config directory: {config_dir}")

    results = bootstrap_configs(PROJECT_ROOT)

    if not results:
        print("No default configs found in repo configs/ directory.")
        return

    created = [name for name, was_created in results.items() if was_created]
    skipped = [name for name, was_created in results.items() if not was_created]

    if created:
        print(f"\nBootstrapped {len(created)} config(s):")
        for name in created:
            print(f"  ✓ {config_dir / name}")

    if skipped:
        print(f"\nSkipped {len(skipped)} config(s) (already exist):")
        for name in skipped:
            print(f"  - {config_dir / name}")

    print(f"\nDone. Edit your configs in: {config_dir}")


if __name__ == "__main__":
    main()
