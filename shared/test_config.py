import pytest
import tempfile
from pathlib import Path

from shared.config import bootstrap_configs


def test_bootstrap_configs_copies_adapters_directory(monkeypatch):
    """bootstrap_configs should copy the adapters/ directory from repo configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_configs = Path(tmpdir) / "configs"
        repo_configs.mkdir()
        (repo_configs / "tools.json").write_text("[]")

        adapters_dir = repo_configs / "adapters"
        adapters_dir.mkdir()
        (adapters_dir / "qwen.sh").write_text("#!/bin/bash\necho qwen")

        user_config = Path(tmpdir) / "user_config"
        user_config.mkdir()

        import shared.config
        monkeypatch.setattr(shared.config, "_get_config_dir", lambda: user_config)

        results = bootstrap_configs(repo_root=Path(tmpdir))
        user_adapters = user_config / "adapters"
        assert user_adapters.exists(), "adapters/ directory was not bootstrapped"
        assert (user_adapters / "qwen.sh").exists(), "qwen.sh was not copied"
        assert results.get("adapters") is True, "adapters should be in results as newly created"
        assert results.get("tools.json") is True, "tools.json should be in results as newly created"
