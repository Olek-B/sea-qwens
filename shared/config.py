"""Platform-aware config path utilities.

Resolves config file locations following the XDG Base Directory Specification:
  - Linux:   ~/.config/sea-qwens/  (or $XDG_CONFIG_HOME/sea-qwens/)
  - macOS:   ~/Library/Application Support/sea-qwens/
  - Windows: %APPDATA%/sea-qwens/

The repo ships with a ``configs/`` directory containing default/example configs.
On first run the user config directory is bootstrapped from those defaults.
"""

import json
import logging
import os
import platform
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config directory resolution
# ---------------------------------------------------------------------------

_APP_NAME = "sea-qwens"


def _get_config_dir() -> Path:
    """Return the user config directory for sea-qwens."""
    system = platform.system()

    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return base / _APP_NAME


def get_tools_config_path() -> Path:
    """Return the full path to the tools.json config file."""
    return _get_config_dir() / "tools.json"


# ---------------------------------------------------------------------------
# Bootstrap / migration helpers
# ---------------------------------------------------------------------------

def ensure_config_dir() -> Path:
    """Create the user config directory if it doesn't exist and return its path."""
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def bootstrap_configs(repo_root: Path | None = None) -> dict[str, bool]:
    """Copy default configs from the repo into the user config directory.

    Returns a dict mapping config filename -> whether it was created
    (``False`` means it already existed).
    """
    if repo_root is None:
        # Best-effort: walk up from this file to find the repo root
        repo_root = Path(__file__).resolve().parent.parent
    else:
        repo_root = Path(repo_root)

    repo_configs = repo_root / "configs"
    user_config_dir = ensure_config_dir()

    results: dict[str, bool] = {}

    if not repo_configs.exists():
        logger.warning(f"Repo configs directory not found: {repo_configs}")
        return results

    for src in repo_configs.iterdir():
        if src.is_file():
            dst = user_config_dir / src.name
            if dst.exists():
                results[src.name] = False
            else:
                shutil.copy2(src, dst)
                logger.info(f"Bootstrapped config: {dst}")
                results[src.name] = True

    return results


def load_tools_config(repo_root: Path | None = None) -> list[dict] | None:
    """Load tools.json from the user config directory, bootstrapping if needed.

    Falls back to the repo's ``configs/`` directory if the user config
    doesn't exist *and* the repo root can be determined — this makes
    Docker builds work when the config is baked in.
    """
    user_path = get_tools_config_path()

    if user_path.exists():
        try:
            with open(user_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read user tools config: {e}")
            return None

    # Bootstrap from repo defaults
    bootstrap_configs(repo_root)

    if user_path.exists():
        try:
            with open(user_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read bootstrapped tools config: {e}")
            return None

    # Last resort: fall back to repo-embedded config (for Docker)
    if repo_root is not None:
        repo_root = Path(repo_root)
        fallback = repo_root / "configs" / "tools.json"
        if fallback.exists():
            logger.warning(f"Using fallback repo config: {fallback}")
            try:
                with open(fallback) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to read fallback tools config: {e}")

    logger.error("No tools config found anywhere")
    return None
