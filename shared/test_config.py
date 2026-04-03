import pytest
import tempfile
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.config import bootstrap_configs, ensure_config_dir


def test_bootstrap_configs_copies_adapters_directory():
    """bootstrap_configs should copy the adapters/ directory from repo configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake repo config structure
        repo_configs = Path(tmpdir) / "configs"
        repo_configs.mkdir()
        (repo_configs / "tools.json").write_text("[]")

        adapters_dir = repo_configs / "adapters"
        adapters_dir.mkdir()
        (adapters_dir / "qwen.sh").write_text("#!/bin/bash\necho qwen")

        # Create a fake user config dir
        user_config = Path(tmpdir) / "user_config"
        user_config.mkdir()

        # Monkey-patch _get_config_dir for this test
        import shared.config
        original_get_config_dir = shared.config._get_config_dir
        shared.config._get_config_dir = lambda: user_config

        try:
            results = bootstrap_configs(repo_root=Path(tmpdir))
            # adapters directory should have been bootstrapped
            user_adapters = user_config / "adapters"
            assert user_adapters.exists(), "adapters/ directory was not bootstrapped"
            assert (user_adapters / "qwen.sh").exists(), "qwen.sh was not copied"
        finally:
            shared.config._get_config_dir = original_get_config_dir
