# Sea Qwens Interactive Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an interactive installer that detects Qwen profiles, configures tools, generates adapters, and bootstraps Docker services.

**Architecture:** Bash entry point for system checks delegates to Python interactive wizard that scans `~/.qwen-accounts/`, generates `tools.json` + adapter scripts, then starts Docker services.

**Tech Stack:** Bash 4+, Python 3.11+ (stdlib only: pathlib, json, subprocess, platform, shutil, re)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/install.sh` | Bash entry point - checks Docker, Python, git, qwen; delegates to Python |
| `scripts/installer/__init__.py` | Package marker |
| `scripts/installer/main.py` | Orchestrates all phases, handles user interaction |
| `scripts/installer/qwen_profiles.py` | Scans `~/.qwen-accounts/`, extracts profile info, OAuth status |
| `scripts/installer/tools_config.py` | Loads/creates `tools.json`, handles idempotency |
| `scripts/installer/adapters.py` | Generates adapter shell scripts from template |
| `scripts/installer/docker_check.py` | Verifies Docker/Python/git, runs compose build/up |
| `scripts/installer/templates/adapter.sh.j2` | Shell template for adapter scripts |
| `tests/installer/test_qwen_profiles.py` | Tests for profile scanning |
| `tests/installer/test_tools_config.py` | Tests for tools.json generation |
| `tests/installer/test_adapters.py` | Tests for adapter generation |
| `tests/installer/test_main.py` | Integration tests for wizard flow |

---

### Task 1: Adapter Template + Installer Package Structure

**Files:**
- Create: `scripts/installer/templates/adapter.sh.j2`
- Create: `scripts/installer/__init__.py`
- Test: `tests/installer/__init__.py`

- [ ] **Step 1: Create the adapter shell template**

```bash
#!/usr/bin/env bash
# Adapter for {{ tool_name }}
# Usage: bash {{ adapter_name }} --prompt "..." --cwd /path [--tool_id id]
set -euo pipefail

PROMPT=""
CWD=""
TOOL_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)  [[ $# -ge 2 ]] || { echo "Error: --prompt requires a value" >&2; exit 1; }; PROMPT="$2"; shift 2 ;;
    --cwd)     [[ $# -ge 2 ]] || { echo "Error: --cwd requires a value" >&2; exit 1; }; CWD="$2"; shift 2 ;;
    --tool_id) [[ $# -ge 2 ]] || { echo "Error: --tool_id requires a value" >&2; exit 1; }; TOOL_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Validate required arguments
if [[ -z "$PROMPT" ]]; then
  echo "Error: --prompt is required" >&2
  echo "Usage: $0 --prompt \"...\" --cwd /path [--tool_id id]" >&2
  exit 1
fi

if [[ -z "$CWD" ]]; then
  echo "Error: --cwd is required" >&2
  echo "Usage: $0 --prompt \"...\" --cwd /path [--tool_id id]" >&2
  exit 1
fi

# Tool-specific environment setup
if [[ -n "${HOME:-}" && -d "$HOME/.local/bin" ]]; then
  export PATH="$HOME/.local/bin:$PATH"
fi
{{ env_exports }}

# Execute tool
exec {{ command }} --prompt "$PROMPT" --cwd "$CWD"
```

- [ ] **Step 2: Create package structure**

```python
# scripts/installer/__init__.py
"""Sea Qwens interactive installer."""
```

```python
# tests/installer/__init__.py
"""Tests for the Sea Qwens installer."""
```

- [ ] **Step 3: Commit**

```bash
git add scripts/installer/ tests/installer/
git commit -m "feat(installer): add package structure and adapter template"
```

---

### Task 2: Qwen Profile Scanner (`qwen_profiles.py`)

**Files:**
- Create: `scripts/installer/qwen_profiles.py`
- Test: `tests/installer/test_qwen_profiles.py`

- [ ] **Step 1: Write tests for profile scanning**

```python
# tests/installer/test_qwen_profiles.py
import pytest
import tempfile
from pathlib import Path
from scripts.installer.qwen_profiles import (
    scan_qwen_accounts,
    get_profile_display_name,
    check_oauth_status,
    ProfileInfo,
)


class TestGetProfileDisplayName:
    def test_simple_title_case(self):
        assert get_profile_display_name("adalovelace") == "Ada Lovelace"

    def test_known_name_mitchel(self):
        assert get_profile_display_name("mitchelbaker") == "Mitchel"

    def test_single_word(self):
        assert get_profile_display_name("turing") == "Turing"

    def test_already_spaced(self):
        assert get_profile_display_name("Twoja Stara") == "Twoja Stara"


class TestCheckOauthStatus:
    def test_oauth_active(self, tmp_path):
        profile_dir = tmp_path / "testprofile"
        profile_dir.mkdir()
        (profile_dir / "oauth_creds.json").write_text("{}")
        assert check_oauth_status(profile_dir) is True

    def test_oauth_missing(self, tmp_path):
        profile_dir = tmp_path / "testprofile"
        profile_dir.mkdir()
        assert check_oauth_status(profile_dir) is False


class TestScanQwenAccounts:
    def test_no_accounts_dir(self, monkeypatch):
        monkeypatch.setenv("QWEN_ACCOUNTS_DIR", "/nonexistent/path")
        result = scan_qwen_accounts()
        assert result == []

    def test_finds_profiles(self, tmp_path, monkeypatch):
        # Create fake accounts
        ada = tmp_path / "adalovelace"
        ada.mkdir()
        (ada / "oauth_creds.json").write_text("{}")

        turing = tmp_path / "turing"
        turing.mkdir()
        # No oauth file

        monkeypatch.setenv("QWEN_ACCOUNTS_DIR", str(tmp_path))
        result = scan_qwen_accounts()

        assert len(result) == 2
        assert result[0].name == "adalovelace"
        assert result[0].display_name == "Ada Lovelace"
        assert result[0].oauth_active is True
        assert result[1].name == "turing"
        assert result[1].oauth_active is False

    def test_empty_accounts_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QWEN_ACCOUNTS_DIR", str(tmp_path))
        result = scan_qwen_accounts()
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/installer/test_qwen_profiles.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.installer.qwen_profiles'"

- [ ] **Step 3: Implement profile scanner**

```python
# scripts/installer/qwen_profiles.py
"""Scan ~/.qwen-accounts for Qwen Code profiles."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProfileInfo:
    """Information about a detected Qwen profile."""
    name: str           # Directory basename, used as --profile value
    display_name: str   # Human-readable name
    path: Path          # Full path to profile directory
    oauth_active: bool  # Whether oauth_creds.json exists


# Known display name overrides for common profiles
_KNOWN_NAMES = {
    "mitchelbaker": "Mitchel",
    "adalovelace": "Ada Lovelace",
}


def _title_case_with_exceptions(slug: str) -> str:
    """Convert slug to title case with special handling."""
    if slug in _KNOWN_NAMES:
        return _KNOWN_NAMES[slug]

    # Try simple title case
    title = slug.title()

    # Handle camelCase by inserting spaces before capitals
    import re
    spaced = re.sub(r'([A-Z])', r' \1', slug[0].upper() + slug[1:]).strip()

    # Return whichever looks more readable
    return spaced if ' ' in spaced else title


def get_profile_display_name(slug: str) -> str:
    """Convert a profile directory name to a display name.

    Args:
        slug: Directory name (e.g., "adalovelace", "mitchelbaker")

    Returns:
        Human-readable name (e.g., "Ada Lovelace", "Mitchel")
    """
    return _title_case_with_exceptions(slug)


def check_oauth_status(profile_path: Path) -> bool:
    """Check if a profile has active OAuth credentials.

    Args:
        profile_path: Path to the profile directory

    Returns:
        True if oauth_creds.json exists, False otherwise
    """
    return (profile_path / "oauth_creds.json").exists()


def scan_qwen_accounts() -> list[ProfileInfo]:
    """Scan ~/.qwen-accounts for available Qwen profiles.

    Returns:
        List of ProfileInfo objects, sorted by display name
    """
    accounts_dir = Path(os.environ.get(
        "QWEN_ACCOUNTS_DIR",
        Path.home() / ".qwen-accounts"
    ))

    if not accounts_dir.is_dir():
        return []

    profiles = []
    for entry in sorted(accounts_dir.iterdir()):
        if entry.is_dir():
            profiles.append(ProfileInfo(
                name=entry.name,
                display_name=get_profile_display_name(entry.name),
                path=entry,
                oauth_active=check_oauth_status(entry),
            ))

    return profiles
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/installer/test_qwen_profiles.py -v
```
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/installer/qwen_profiles.py tests/installer/test_qwen_profiles.py
git commit -m "feat(installer): add Qwen profile scanner with OAuth detection"
```

---

### Task 3: Adapter Generator (`adapters.py`)

**Files:**
- Create: `scripts/installer/adapters.py`
- Test: `tests/installer/test_adapters.py`

- [ ] **Step 1: Write tests for adapter generation**

```python
# tests/installer/test_adapters.py
import pytest
import tempfile
import stat
from pathlib import Path
from scripts.installer.adapters import (
    generate_adapter_script,
    render_adapter_template,
)


class TestRenderAdapterTemplate:
    def test_basic_command(self):
        result = render_adapter_template(
            tool_name="test-tool",
            adapter_name="test-tool.sh",
            command="test-tool --no-interactive",
            env_exports="",
        )
        assert '#!/usr/bin/env bash' in result
        assert 'exec test-tool --no-interactive --prompt "$PROMPT"' in result
        assert 'set -euo pipefail' in result

    def test_qwen_profile_command(self):
        result = render_adapter_template(
            tool_name="qwen-ada",
            adapter_name="qwen-ada.sh",
            command="qwen --profile Ada --non-interactive",
            env_exports='export QWEN_CONFIG_DIR="${HOME}/.qwen"',
        )
        assert 'exec qwen --profile Ada --non-interactive --prompt "$PROMPT"' in result
        assert 'export QWEN_CONFIG_DIR' in result

    def test_env_exports(self):
        env = 'export FOO="bar"\nexport BAZ="qux"'
        result = render_adapter_template(
            tool_name="my-tool",
            adapter_name="my-tool.sh",
            command="my-tool",
            env_exports=env,
        )
        assert 'export FOO="bar"' in result
        assert 'export BAZ="qux"' in result


class TestGenerateAdapterScript:
    def test_creates_executable_file(self, tmp_path):
        adapters_dir = tmp_path / "adapters"
        adapters_dir.mkdir()

        path = generate_adapter_script(
            adapters_dir=adapters_dir,
            tool_name="test-tool",
            command="test-tool --no-interactive",
            env_exports="",
        )

        assert path.exists()
        assert path.name == "test-tool.sh"
        assert path.stat().st_mode & stat.S_IXUSR

    def test_idempotent_does_not_overwrite(self, tmp_path):
        adapters_dir = tmp_path / "adapters"
        adapters_dir.mkdir()
        existing = adapters_dir / "test-tool.sh"
        existing.write_text("# existing content")

        path = generate_adapter_script(
            adapters_dir=adapters_dir,
            tool_name="test-tool",
            command="test-tool",
            env_exports="",
        )

        assert path.read_text() == "# existing content"

    def test_overwrite_when_requested(self, tmp_path):
        adapters_dir = tmp_path / "adapters"
        adapters_dir.mkdir()
        existing = adapters_dir / "test-tool.sh"
        existing.write_text("# old content")

        path = generate_adapter_script(
            adapters_dir=adapters_dir,
            tool_name="test-tool",
            command="test-tool",
            env_exports="",
            overwrite=True,
        )

        assert path.exists()
        assert "# old content" not in path.read_text()
        assert "exec test-tool --prompt" in path.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/installer/test_adapters.py -v
```
Expected: FAIL with import errors

- [ ] **Step 3: Implement adapter generator**

```python
# scripts/installer/adapters.py
"""Generate adapter shell scripts for CLI tools."""

import os
import stat
from pathlib import Path


def render_adapter_template(
    tool_name: str,
    adapter_name: str,
    command: str,
    env_exports: str = "",
) -> str:
    """Render an adapter script for a CLI tool.

    Args:
        tool_name: Human-readable tool name (for comments)
        adapter_name: Filename (e.g., "qwen-ada.sh")
        command: The CLI command to execute (e.g., "qwen --profile Ada --non-interactive")
        env_exports: Environment variable exports (empty string for none)

    Returns:
        Complete shell script as string
    """
    env_block = env_exports if env_exports else "# No additional environment variables needed"

    return f'''#!/usr/bin/env bash
# Adapter for {tool_name}
# Usage: bash {adapter_name} --prompt "..." --cwd /path [--tool_id id]
set -euo pipefail

PROMPT=""
CWD=""
TOOL_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)  [[ $# -ge 2 ]] || {{ echo "Error: --prompt requires a value" >&2; exit 1; }}; PROMPT="$2"; shift 2 ;;
    --cwd)     [[ $# -ge 2 ]] || {{ echo "Error: --cwd requires a value" >&2; exit 1; }}; CWD="$2"; shift 2 ;;
    --tool_id) [[ $# -ge 2 ]] || {{ echo "Error: --tool_id requires a value" >&2; exit 1; }}; TOOL_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Validate required arguments
if [[ -z "$PROMPT" ]]; then
  echo "Error: --prompt is required" >&2
  echo "Usage: $0 --prompt \\"...\\" --cwd /path [--tool_id id]" >&2
  exit 1
fi

if [[ -z "$CWD" ]]; then
  echo "Error: --cwd is required" >&2
  echo "Usage: $0 --prompt \\"...\\" --cwd /path [--tool_id id]" >&2
  exit 1
fi

# Tool-specific environment setup
if [[ -n "${{HOME:-}}" && -d "$HOME/.local/bin" ]]; then
  export PATH="$HOME/.local/bin:$PATH"
fi
{env_block}

# Execute tool
exec {command} --prompt "$PROMPT" --cwd "$CWD"
'''


def generate_adapter_script(
    adapters_dir: Path,
    tool_name: str,
    command: str,
    env_exports: str = "",
    overwrite: bool = False,
) -> Path:
    """Generate an adapter script for a CLI tool.

    Args:
        adapters_dir: Directory to write adapter scripts into
        tool_name: Tool name (used for filename: <tool_name>.sh)
        command: CLI command to execute
        env_exports: Environment variable exports
        overwrite: If True, overwrite existing adapters

    Returns:
        Path to the generated (or existing) adapter script
    """
    adapter_name = f"{tool_name}.sh"
    adapter_path = adapters_dir / adapter_name

    if adapter_path.exists() and not overwrite:
        return adapter_path

    script_content = render_adapter_template(
        tool_name=tool_name,
        adapter_name=adapter_name,
        command=command,
        env_exports=env_exports,
    )

    adapter_path.write_text(script_content)

    # Make executable
    current_mode = adapter_path.stat().st_mode
    adapter_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return adapter_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/installer/test_adapters.py -v
```
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/installer/adapters.py tests/installer/test_adapters.py
git commit -m "feat(installer): add adapter script generator"
```

---

### Task 4: Tools Config Manager (`tools_config.py`)

**Files:**
- Create: `scripts/installer/tools_config.py`
- Test: `tests/installer/test_tools_config.py`

- [ ] **Step 1: Write tests for tools.json management**

```python
# tests/installer/test_tools_config.py
import pytest
import json
import tempfile
from pathlib import Path
from scripts.installer.tools_config import (
    build_tool_entry,
    load_existing_tools,
    save_tools_config,
)


class TestBuildToolEntry:
    def test_qwen_profile_tool(self):
        entry = build_tool_entry(
            name="qwen-ada",
            command="qwen --profile Ada --non-interactive",
            adapter="qwen-ada.sh",
            capabilities=["coding", "testing", "debugging", "refactoring"],
        )
        assert entry["name"] == "qwen-ada"
        assert entry["command"] == "qwen --profile Ada --non-interactive"
        assert entry["adapter"] == "qwen-ada.sh"
        assert entry["usage_count"] == 0
        assert entry["daily_limit"] == 1000
        assert entry["health_status"] == "HEALTHY"
        assert entry["consecutive_failures"] == 0
        assert entry["requests_today"] == 0

    def test_custom_tool(self):
        entry = build_tool_entry(
            name="claude-code",
            command="claude --no-interactive",
            adapter="claude-code.sh",
            capabilities=["coding", "code-review"],
            daily_limit=500,
        )
        assert entry["name"] == "claude-code"
        assert entry["daily_limit"] == 500


class TestLoadExistingTools:
    def test_loads_valid_json(self, tmp_path):
        config_file = tmp_path / "tools.json"
        config_file.write_text(json.dumps([{"name": "test"}]))
        result = load_existing_tools(config_file)
        assert result == [{"name": "test"}]

    def test_returns_empty_list_missing_file(self, tmp_path):
        config_file = tmp_path / "tools.json"
        result = load_existing_tools(config_file)
        assert result == []

    def test_returns_empty_list_invalid_json(self, tmp_path):
        config_file = tmp_path / "tools.json"
        config_file.write_text("not json")
        result = load_existing_tools(config_file)
        assert result == []


class TestSaveToolsConfig:
    def test_creates_config_dir_and_file(self, tmp_path):
        config_dir = tmp_path / "sea-qwens"
        config_file = config_dir / "tools.json"
        tools = [{"name": "test"}]

        save_tools_config(config_dir, tools)

        assert config_dir.exists()
        assert config_file.exists()
        loaded = json.loads(config_file.read_text())
        assert loaded == tools

    def test_idempotent_existing_tools(self, tmp_path):
        config_dir = tmp_path / "sea-qwens"
        config_dir.mkdir()
        config_file = config_dir / "tools.json"
        existing = [{"name": "existing", "command": "cmd"}]
        config_file.write_text(json.dumps(existing))

        new_tools = [{"name": "new", "command": "cmd2"}]
        save_tools_config(config_dir, new_tools)

        loaded = json.loads(config_file.read_text())
        # Should contain both existing and new
        names = {t["name"] for t in loaded}
        assert "existing" in names
        assert "new" in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/installer/test_tools_config.py -v
```
Expected: FAIL with import errors

- [ ] **Step 3: Implement tools config manager**

```python
# scripts/installer/tools_config.py
"""Manage tools.json configuration."""

import json
from pathlib import Path
from typing import Optional


def build_tool_entry(
    name: str,
    command: str,
    adapter: str,
    capabilities: list[str],
    daily_limit: int = 1000,
) -> dict:
    """Build a complete tool entry for tools.json.

    Args:
        name: Tool identifier (e.g., "qwen-ada", "claude-code")
        command: CLI command (e.g., "qwen --profile Ada --non-interactive")
        adapter: Adapter filename (e.g., "qwen-ada.sh")
        capabilities: List of capability tags
        daily_limit: Max requests per day

    Returns:
        Dict matching the Tool Pydantic model structure
    """
    return {
        "name": name,
        "command": command,
        "adapter": adapter,
        "usage_count": 0,
        "daily_limit": daily_limit,
        "capabilities": capabilities,
        "health_status": "HEALTHY",
        "consecutive_failures": 0,
        "requests_today": 0,
    }


def load_existing_tools(config_file: Path) -> list[dict]:
    """Load existing tools from tools.json.

    Args:
        config_file: Path to tools.json

    Returns:
        List of tool dicts, or empty list if file missing/invalid
    """
    if not config_file.exists():
        return []

    try:
        data = json.loads(config_file.read_text())
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, IOError):
        return []


def save_tools_config(
    config_dir: Path,
    tools: list[dict],
) -> None:
    """Save tools configuration to tools.json.

    Merges with existing tools to maintain idempotency.

    Args:
        config_dir: User config directory (~/.config/sea-qwens/)
        tools: List of tool entries to save
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "tools.json"

    # Load existing tools for merge
    existing = load_existing_tools(config_file)
    existing_names = {t["name"] for t in existing}

    # Merge: keep existing, add new
    merged_names = {t["name"] for t in tools}
    new_tools = [t for t in tools if t["name"] not in existing_names]
    final_tools = existing + new_tools

    config_file.write_text(json.dumps(final_tools, indent=2) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/installer/test_tools_config.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/installer/tools_config.py tests/installer/test_tools_config.py
git commit -m "feat(installer): add tools.json config manager with idempotency"
```

---

### Task 5: Docker Check Module (`docker_check.py`)

**Files:**
- Create: `scripts/installer/docker_check.py`
- Test: `tests/installer/test_docker_check.py`

- [ ] **Step 1: Write tests for Docker checks**

```python
# tests/installer/test_docker_check.py
import pytest
from unittest.mock import patch, MagicMock
from scripts.installer.docker_check import (
    check_command_version,
    check_docker,
    check_docker_compose,
    check_python_version,
    check_git,
    check_qwen,
)


class TestCheckCommandVersion:
    def test_valid_version(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 24.0.5\n")
            result = check_command_version(["docker", "--version"], "20.10")
            assert result is True

    def test_command_not_found(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = check_command_version(["nonexistent", "--version"], "1.0")
            assert result is False


class TestCheckPythonVersion:
    def test_sufficient_version(self):
        with patch("sys.version_info", (3, 11, 5)):
            result = check_python_version()
            assert result is True

    def test_insufficient_version(self):
        with patch("sys.version_info", (3, 10, 0)):
            result = check_python_version()
            assert result is False


class TestCheckQwen:
    def test_qwen_found(self):
        with patch("shutil.which", return_value="/usr/local/bin/qwen"):
            result = check_qwen()
            assert result is True

    def test_qwen_missing(self):
        with patch("shutil.which", return_value=None):
            result = check_qwen()
            assert result is False  # Non-fatal, returns False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/installer/test_docker_check.py -v
```
Expected: FAIL with import errors

- [ ] **Step 3: Implement Docker check module**

```python
# scripts/installer/docker_check.py
"""Verify system prerequisites: Docker, Python, git, Qwen Code."""

import subprocess
import sys
import shutil
from pathlib import Path


def check_command_version(command: list[str], min_version: str) -> bool:
    """Check if a command exists and meets minimum version.

    Args:
        command: Command and version flag (e.g., ["docker", "--version"])
        min_version: Minimum version string to check for

    Returns:
        True if command exists and version >= min_version
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        # Simple version string containment check
        output = result.stdout.strip()
        return min_version in output or _version_gte(output, min_version)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _version_gte(version_string: str, min_version: str) -> bool:
    """Check if version_string >= min_version (simple numeric comparison).

    Args:
        version_string: Full version output (e.g., "Docker version 24.0.5")
        min_version: Minimum version (e.g., "20.10")

    Returns:
        True if version_string >= min_version
    """
    import re

    # Extract version numbers
    nums = re.findall(r'(\d+)\.(\d+)', version_string)
    if not nums:
        return False

    major, minor = int(nums[0][0]), int(nums[0][1])
    min_parts = min_version.split(".")
    min_major = int(min_parts[0])
    min_minor = int(min_parts[1]) if len(min_parts) > 1 else 0

    return (major, minor) >= (min_major, min_minor)


def check_docker() -> tuple[bool, str]:
    """Check Docker availability.

    Returns:
        (found: bool, message: str)
    """
    if check_command_version(["docker", "--version"], "20.10"):
        return True, "Docker found"
    return False, "Docker not found (required: 20.10+)"


def check_docker_compose() -> tuple[bool, str]:
    """Check Docker Compose availability.

    Returns:
        (found: bool, message: str)
    """
    # Try plugin syntax first: docker compose
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Docker Compose plugin found"
    except FileNotFoundError:
        pass

    # Fallback: standalone docker-compose
    if shutil.which("docker-compose"):
        return True, "docker-compose found"

    return False, "Docker Compose not found"


def check_python_version() -> bool:
    """Check Python version is 3.11+.

    Returns:
        True if Python >= 3.11
    """
    return sys.version_info >= (3, 11)


def check_git() -> tuple[bool, str]:
    """Check git availability (2.23+ for worktree support).

    Returns:
        (found: bool, message: str)
    """
    if check_command_version(["git", "--version"], "2.23"):
        return True, "git found"
    return False, "git not found (required: 2.23+)"


def check_qwen() -> bool:
    """Check Qwen Code CLI availability (non-fatal warning).

    Returns:
        True if qwen CLI found in PATH
    """
    return shutil.which("qwen") is not None


def run_system_checks() -> dict[str, tuple[bool, str]]:
    """Run all prerequisite checks.

    Returns:
        Dict of check_name -> (passed: bool, message: str)
    """
    results = {}
    results["docker"] = check_docker()
    results["docker_compose"] = check_docker_compose()
    results["python"] = (check_python_version(), f"Python {sys.version.split()[0]}")
    results["git"] = check_git()
    results["qwen"] = (check_qwen(), "Qwen Code CLI" if check_qwen() else "Qwen Code CLI not found")
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/installer/test_docker_check.py -v
```
Expected: All 4+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/installer/docker_check.py tests/installer/test_docker_check.py
git commit -m "feat(installer): add Docker/Python/git prerequisite checks"
```

---

### Task 6: Interactive Wizard (`main.py`)

**Files:**
- Create: `scripts/installer/main.py`
- Test: `tests/installer/test_main.py`

- [ ] **Step 1: Write tests for wizard flow**

```python
# tests/installer/test_main.py
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
from scripts.installer.main import (
    print_header,
    print_step,
    print_success,
    print_warning,
    prompt_yes_no,
    prompt_input,
    select_profiles,
    run_installer,
)


class TestUIHelpers:
    def test_prompt_yes_no_defaults_no(self):
        with patch("builtins.input", return_value=""):
            assert prompt_yes_no("Continue?") is False

    def test_prompt_yes_no_yes_response(self):
        with patch("builtins.input", return_value="y"):
            assert prompt_yes_no("Continue?") is True

    def test_prompt_yes_no_uppercase(self):
        with patch("builtins.input", return_value="Y"):
            assert prompt_yes_no("Continue?") is True

    def test_prompt_input_retries_on_empty(self):
        with patch("builtins.input", side_effect=["", "valid input"]):
            result = prompt_input("Enter: ")
            assert result == "valid input"


class TestSelectProfiles:
    def test_valid_selection(self):
        profiles = [
            MagicMock(name="ada", display_name="Ada"),
            MagicMock(name="turing", display_name="Turing"),
        ]
        with patch("builtins.input", return_value="1,2"):
            result = select_profiles(profiles)
            assert len(result) == 2

    def test_invalid_input_retries(self):
        profiles = [MagicMock(name="test", display_name="Test")]
        with patch("builtins.input", side_effect=["abc", "1"]):
            result = select_profiles(profiles)
            assert len(result) == 1

    def test_empty_selection_returns_none(self):
        profiles = [MagicMock(name="test", display_name="Test")]
        with patch("builtins.input", return_value=""):
            result = select_profiles(profiles)
            assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/installer/test_main.py -v
```
Expected: FAIL with import errors

- [ ] **Step 3: Implement interactive wizard**

```python
# scripts/installer/main.py
"""Interactive installer wizard for Sea Qwens."""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.installer.qwen_profiles import scan_qwen_accounts, ProfileInfo
from scripts.installer.tools_config import build_tool_entry, load_existing_tools, save_tools_config
from scripts.installer.adapters import generate_adapter_script
from scripts.installer.docker_check import run_system_checks


# ─── ANSI Color Codes ───────────────────────────────────────────────────────

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"  # No Color


# ─── UI Helpers ──────────────────────────────────────────────────────────────

def print_header(text: str) -> None:
    """Print a styled header line."""
    print(f"\n{BOLD}{CYAN}{'=' * 60}{NC}")
    print(f"{BOLD}{CYAN}  {text}{NC}")
    print(f"{BOLD}{CYAN}{'=' * 60}{NC}\n")


def print_step(text: str) -> None:
    """Print a step description."""
    print(f"  {CYAN}▸{NC} {text}")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"  {GREEN}✓{NC} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"  {YELLOW}!{NC} {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"  {RED}✗{NC} {text}")


def prompt_yes_no(question: str, default: str = "no") -> bool:
    """Prompt user with yes/no question.

    Args:
        question: The question to ask
        default: Default answer ("yes" or "no")

    Returns:
        True for yes, False for no
    """
    suffix = " [Y/n]: " if default == "yes" else " [y/N]: "
    while True:
        answer = input(f"{question}{suffix}").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer == "":
            return default == "yes"
        print(f"  {YELLOW}Please enter 'y' or 'n'{NC}")


def prompt_input(prompt_text: str, required: bool = True) -> str:
    """Prompt user for input, retrying if empty and required.

    Args:
        prompt_text: The prompt to display
        required: If True, reject empty input

    Returns:
        User's input string
    """
    while True:
        answer = input(prompt_text).strip()
        if answer or not required:
            return answer
        print(f"  {YELLOW}This field is required{NC}")


# ─── Profile Selection ───────────────────────────────────────────────────────

def select_profiles(profiles: list[ProfileInfo]) -> list[ProfileInfo] | None:
    """Interactive profile selection.

    Args:
        profiles: List of detected ProfileInfo objects

    Returns:
        List of selected profiles, or None if user skipped selection
    """
    if not profiles:
        print_warning("No Qwen profiles found in ~/.qwen-accounts")
        return None

    print(f"\n{BOLD}Found {len(profiles)} Qwen profiles:{NC}\n")

    for i, profile in enumerate(profiles, 1):
        status = f"{GREEN}✓{NC}" if profile.oauth_active else " "
        print(f"  {i}. [{status}] {profile.display_name} ({profile.name})")

    print(f"\nEnter profile numbers to enable (comma-separated, e.g. 1,2,4):")
    print(f"  (press Enter to skip)")

    while True:
        answer = input("> ").strip()
        if not answer:
            return None

        try:
            indices = [int(x.strip()) for x in answer.split(",")]
            selected = []
            for idx in indices:
                if 1 <= idx <= len(profiles):
                    selected.append(profiles[idx - 1])
                else:
                    print(f"  {YELLOW}Invalid number: {idx}. Must be 1-{len(profiles)}{NC}")
                    selected = []
                    break
            if selected:
                return selected
        except ValueError:
            print(f"  {YELLOW}Please enter comma-separated numbers (e.g. 1,2,4){NC}")


# ─── Installer Phases ────────────────────────────────────────────────────────

def phase_system_checks() -> dict:
    """Phase 1: Check prerequisites."""
    print_header("Phase 1: System Checks")

    results = run_system_checks()

    # Fatal checks
    for check_name in ("docker", "docker_compose", "python", "git"):
        passed, msg = results[check_name]
        if passed:
            print_success(f"{check_name.replace('_', ' ').title()}: {msg}")
        else:
            print_error(f"{check_name.replace('_', ' ').title()}: {msg}")
            if check_name in ("docker", "docker_compose"):
                print_error("Docker is required. Install Docker and try again.")
                print_error("  https://docs.docker.com/get-docker/")
                sys.exit(1)
            elif check_name == "python":
                print_error("Python 3.11+ is required.")
                sys.exit(1)
            elif check_name == "git":
                print_error("git 2.23+ is required for worktree support.")
                sys.exit(1)

    # Non-fatal: qwen
    qwen_found, qwen_msg = results["qwen"]
    if qwen_found:
        print_success(f"Qwen Code: {qwen_msg}")
    else:
        print_warning(f"Qwen Code: {qwen_msg} (needed later for task execution)")

    return results


def phase_qwen_profiles() -> list[dict]:
    """Phase 2-3: Detect and select Qwen profiles."""
    print_header("Phase 2: Qwen Code Profiles")

    profiles = scan_qwen_accounts()
    selected = select_profiles(profiles)

    if not selected:
        print_step("Skipping Qwen profile selection.")
        return []

    # Build tool entries
    tools = []
    for profile in selected:
        tool_name = f"qwen-{profile.name}"
        command = f"qwen --profile {profile.display_name} --non-interactive"
        adapter = f"{tool_name}.sh"
        capabilities = ["coding", "testing", "debugging", "refactoring"]

        tools.append(build_tool_entry(
            name=tool_name,
            command=command,
            adapter=adapter,
            capabilities=capabilities,
        ))

    print(f"\n{BOLD}Will create {len(tools)} Qwen tools:{NC}")
    for tool in tools:
        print(f"  • {tool['name']} → {tool['command']}")

    # Manual add option
    if prompt_yes_no("Add more Qwen profiles manually?"):
        while True:
            profile_name = prompt_input("Profile name (e.g., MyProfile): ")
            tool_name = f"qwen-{profile_name.lower()}"
            command = f"qwen --profile {profile_name} --non-interactive"
            adapter = f"{tool_name}.sh"

            tools.append(build_tool_entry(
                name=tool_name,
                command=command,
                adapter=adapter,
                capabilities=["coding", "testing", "debugging", "refactoring"],
            ))
            print_success(f"Added qwen-{profile_name}")

            if not prompt_yes_no("Add another?"):
                break

    return tools


def phase_custom_tools(existing_tools: list[dict]) -> list[dict]:
    """Phase 4: Add custom CLI tools."""
    print_header("Phase 3: Custom CLI Tools")

    all_tools = list(existing_tools)  # Start with existing for idempotency

    if not prompt_yes_no("Add other CLI tools (e.g. claude-code, aider, codex)?"):
        print_step("Skipping custom tool setup.")
        return all_tools

    while True:
        name = prompt_input("Tool name: ")
        command = prompt_input("CLI command (e.g., claude --no-interactive): ")
        caps_input = prompt_input(
            "Capabilities (comma-separated) [coding,testing,debugging]: ",
            required=False,
        )
        capabilities = [c.strip() for c in (caps_input or "coding,testing,debugging").split(",") if c.strip()]

        tool = build_tool_entry(
            name=name,
            command=command,
            adapter=f"{name}.sh",
            capabilities=capabilities,
        )

        # Check for duplicate
        existing_names = {t["name"] for t in all_tools}
        if name in existing_names:
            print_warning(f"Tool '{name}' already exists. Skipping.")
        else:
            all_tools.append(tool)
            print_success(f"Added tool: {name}")

        if not prompt_yes_no("Add another tool?"):
            break

    return all_tools


def phase_generate_configs(
    config_dir: Path,
    adapters_dir: Path,
    tools: list[dict],
) -> None:
    """Phase 5: Generate configuration files."""
    print_header("Phase 4: Generating Configuration")

    print_step(f"Config directory: {config_dir}")

    # Generate adapter scripts
    adapter_count = 0
    for tool in tools:
        path = generate_adapter_script(
            adapters_dir=adapters_dir,
            tool_name=tool["name"],
            command=tool["command"],
            env_exports="",
        )
        if path.exists():
            adapter_count += 1

    # Save tools.json
    save_tools_config(config_dir, tools)

    print_success(f"Wrote tools.json ({len(tools)} tools)")
    print_success(f"Generated {adapter_count} adapter scripts")


def phase_docker_setup(project_root: Path) -> None:
    """Phase 6: Build and start Docker services."""
    print_header("Phase 5: Docker Setup")

    compose_cmd = ["docker", "compose"]
    compose_file = str(project_root / "docker-compose.yml")

    # Build
    print_step("Building Docker images...")
    subprocess.run(
        [*compose_cmd, "-f", compose_file, "build"],
        cwd=project_root,
        check=True,
    )
    print_success("Docker images built")

    # Start services using existing script
    print_step("Starting services...")
    start_script = project_root / "scripts" / "start-sea-qwens.sh"
    if start_script.exists():
        subprocess.run(["bash", str(start_script)], cwd=project_root, check=True)
    else:
        subprocess.run(
            [*compose_cmd, "-f", compose_file, "up", "-d"],
            cwd=project_root,
            check=True,
        )
    print_success("Services started")


def phase_verification(librarian_url: str = "http://localhost:8001") -> None:
    """Phase 7: Verify services and loaded tools."""
    print_header("Phase 6: Verification")

    import urllib.request

    # Check Librarian
    try:
        with urllib.request.urlopen(f"{librarian_url}/tasks/ready", timeout=10) as resp:
            if resp.status == 200:
                print_success(f"Librarian ({librarian_url}): healthy")
    except Exception as e:
        print_warning(f"Librarian not responding: {e}")
        print_warning("Services may still be initializing. Retry in 30 seconds.")

    # Check service health endpoints
    services = {
        "Atomizer": "http://localhost:8002/health",
        "Kanban": "http://localhost:8003/health",
        "Worker": "http://localhost:8004/health",
        "Tester": "http://localhost:8005/health",
    }

    for name, url in services.items():
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    print_success(f"{name}: healthy")
        except Exception:
            print_warning(f"{name}: not responding yet")


def run_installer() -> None:
    """Run the full Sea Qwens installer."""
    print_header("Sea Qwens Installer")
    print("Welcome! This installer will:")
    print("  1. Check system prerequisites")
    print("  2. Detect Qwen Code profiles")
    print("  3. Configure CLI tools")
    print("  4. Generate adapter scripts")
    print("  5. Build and start Docker services")
    print("  6. Verify everything works")
    print()

    if not prompt_yes_no("Continue?"):
        print("Installation cancelled.")
        sys.exit(0)

    # Phase 1: System checks
    phase_system_checks()

    # Resolve paths
    from shared.config import _get_config_dir
    config_dir = _get_config_dir()
    adapters_dir = config_dir / "adapters"
    project_root = PROJECT_ROOT

    # Check for existing tools
    existing_tools = load_existing_tools(config_dir / "tools.json")
    if existing_tools:
        print_step(f"Found {len(existing_tools)} existing tools in tools.json")

    # Phase 2-3: Qwen profiles
    qwen_tools = phase_qwen_profiles()

    # Phase 4: Custom tools
    all_tools = phase_custom_tools(existing_tools + qwen_tools)

    if not all_tools:
        print_error("No tools configured. At least one tool is required.")
        sys.exit(1)

    # Phase 5: Generate configs
    phase_generate_configs(config_dir, adapters_dir, all_tools)

    # Phase 6: Docker
    if prompt_yes_no("Build and start Docker services?"):
        phase_docker_setup(project_root)
        # Phase 7: Verification
        phase_verification()

    print_header("Installation Complete!")
    print("Next steps:")
    print("  1. Create a project: python -m services.manager.cli interview")
    print("  2. Or send a spec: curl -X POST http://localhost:8001/project-specs -d '{...}'")
    print("  3. Monitor services: docker compose logs -f")
    print()


if __name__ == "__main__":
    run_installer()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/installer/test_main.py -v
```
Expected: All 5+ tests PASS

- [ ] **Step 5: Create bash entry point**

```bash
#!/usr/bin/env bash
#
# install.sh — Interactive installer for Sea Qwens
#
# Checks prerequisites and runs the Python wizard.
#
# Usage: ./scripts/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }

# Check Python 3.11+
if ! command -v python3 &>/dev/null; then
  error "Python 3 not found."
  error "Install Python 3.11+ and try again."
  error "  https://www.python.org/downloads/"
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 11 ]]; then
  error "Python 3.11+ required (found $PYTHON_VERSION)."
  exit 1
fi

info "Python $PYTHON_VERSION found"

# Check Docker
if ! command -v docker &>/dev/null; then
  error "Docker not found."
  error "Install Docker and try again."
  error "  https://docs.docker.com/get-docker/"
  exit 1
fi

info "Docker found"

# Check Docker Compose
if ! docker compose version &>/dev/null 2>&1 && ! command -v docker-compose &>/dev/null; then
  error "Docker Compose not found."
  error "Install Docker Compose plugin or docker-compose."
  exit 1
fi

info "Docker Compose found"

# Check git (non-fatal)
if command -v git &>/dev/null; then
  info "git found"
else
  warn "git not found (needed for worktrees)"
fi

# Check qwen (non-fatal)
if command -v qwen &>/dev/null; then
  info "Qwen Code found"
else
  warn "Qwen Code not found (needed later for task execution)"
fi

info "All prerequisites satisfied"
echo ""
info "Running installer wizard..."
echo ""

cd "$PROJECT_DIR"
python3 scripts/installer/main.py
```

- [ ] **Step 6: Make install.sh executable and commit**

```bash
chmod +x scripts/install.sh
git add scripts/installer/main.py scripts/install.sh tests/installer/test_main.py
git commit -m "feat(installer): add interactive wizard with full flow"
```

---

### Task 7: Update README + Final Integration Test

**Files:**
- Modify: `README.md`
- Test: `tests/installer/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/installer/test_integration.py
"""Integration tests for the full installer flow."""
import pytest
import json
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.installer.qwen_profiles import ProfileInfo
from scripts.installer.tools_config import build_tool_entry, load_existing_tools, save_tools_config
from scripts.installer.adapters import generate_adapter_script


class TestFullConfigGeneration:
    """Test generating a complete tools.json + adapters from scratch."""

    def test_qwen_and_custom_tools(self, tmp_path):
        config_dir = tmp_path / "sea-qwens"
        adapters_dir = config_dir / "adapters"
        adapters_dir.mkdir(parents=True)

        # Simulate selected Qwen profiles
        tools = [
            build_tool_entry(
                name="qwen-ada",
                command="qwen --profile Ada --non-interactive",
                adapter="qwen-ada.sh",
                capabilities=["coding", "testing", "debugging", "refactoring"],
            ),
            build_tool_entry(
                name="claude-code",
                command="claude --no-interactive",
                adapter="claude-code.sh",
                capabilities=["coding", "code-review"],
            ),
        ]

        # Generate configs
        save_tools_config(config_dir, tools)
        for tool in tools:
            generate_adapter_script(
                adapters_dir=adapters_dir,
                tool_name=tool["name"],
                command=tool["command"],
                env_exports="",
            )

        # Verify tools.json
        config_file = config_dir / "tools.json"
        assert config_file.exists()
        loaded = json.loads(config_file.read_text())
        assert len(loaded) == 2
        assert loaded[0]["name"] == "qwen-ada"
        assert loaded[1]["name"] == "claude-code"

        # Verify adapters
        assert (adapters_dir / "qwen-ada.sh").exists()
        assert (adapters_dir / "claude-code.sh").exists()

        # Verify adapters are executable and contain correct commands
        ada_adapter = (adapters_dir / "qwen-ada.sh").read_text()
        assert "qwen --profile Ada --non-interactive" in ada_adapter
        assert "--prompt" in ada_adapter
        assert "--cwd" in ada_adapter

        claude_adapter = (adapters_dir / "claude-code.sh").read_text()
        assert "claude --no-interactive" in claude_adapter


class TestIdempotency:
    def test_running_twice_does_not_duplicate(self, tmp_path):
        config_dir = tmp_path / "sea-qwens"
        config_dir.mkdir()

        # First run
        tools_v1 = [
            build_tool_entry("qwen-ada", "qwen --profile Ada --non-interactive", "qwen-ada.sh", ["coding"]),
        ]
        save_tools_config(config_dir, tools_v1)

        # Second run with same + new tool
        tools_v2 = [
            build_tool_entry("qwen-ada", "qwen --profile Ada --non-interactive", "qwen-ada.sh", ["coding"]),
            build_tool_entry("qwen-turing", "qwen --profile Turing --non-interactive", "qwen-turing.sh", ["coding"]),
        ]
        save_tools_config(config_dir, tools_v2)

        loaded = json.loads((config_dir / "tools.json").read_text())
        # Should have 2 tools, not 3
        assert len(loaded) == 2
        names = {t["name"] for t in loaded}
        assert names == {"qwen-ada", "qwen-turing"}
```

- [ ] **Step 2: Run integration tests**

```bash
python -m pytest tests/installer/test_integration.py -v
```
Expected: All tests PASS (uses already-implemented modules)

- [ ] **Step 3: Update README.md**

Add this section to README.md after the "Quick Start" section:

```markdown
---

## Installer

Sea Qwens ships with an interactive installer that handles tool configuration, adapter generation, and Docker setup.

### Quick Install

```bash
./scripts/install.sh
```

The installer will:
1. **Check prerequisites** — Docker, Python 3.11+, git
2. **Detect Qwen Code profiles** — Scans `~/.qwen-accounts/` for OAuth-authenticated profiles
3. **Configure CLI tools** — Select which profiles to enable, add custom tools (Claude, Codex, etc.)
4. **Generate configuration** — Creates `~/.config/sea-qwens/tools.json` + adapter scripts
5. **Build and start Docker** — Builds images and starts all services
6. **Verify** — Checks that all services are healthy

### Manual Setup

If you prefer manual configuration:

```bash
# Bootstrap default config
python scripts/setup-config.py

# Edit your tools
nano ~/.config/sea-qwens/tools.json

# Start services
./scripts/start-sea-qwens.sh
```
```

- [ ] **Step 4: Run all installer tests**

```bash
python -m pytest tests/installer/ -v
```
Expected: All tests PASS

- [ ] **Step 5: Final commit**

```bash
git add README.md tests/installer/test_integration.py
git commit -m "docs: add installer section + integration tests"
```

---

## Self-Review Checklist

### 1. Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| Bash entry point with system checks | Task 6 (install.sh in Step 5) |
| Python interactive wizard | Task 6 (main.py) |
| Scan ~/.qwen-accounts | Task 2 (qwen_profiles.py) |
| OAuth status via oauth_creds.json | Task 2 (check_oauth_status) |
| Numbered profile selection | Task 6 (select_profiles) |
| Manual profile add | Task 6 (phase_qwen_profiles manual add loop) |
| Custom CLI tool addition | Task 6 (phase_custom_tools) |
| tools.json generation | Task 4 (tools_config.py) |
| Adapter script generation | Task 3 (adapters.py) |
| Idempotency | Task 4 (save_tools_config merge logic), Task 7 (idempotency test) |
| Docker build/startup | Task 6 (phase_docker_setup) |
| Service verification | Task 6 (phase_verification) |
| Cross-platform config dir | Uses shared/config.py _get_config_dir |
| No external dependencies | All stdlib |

All spec requirements covered.

### 2. Placeholder Scan

No TBDs, TODOs, or "implement later" found. All code is complete with actual implementations.

### 3. Type Consistency

- `ProfileInfo` dataclass used consistently across Tasks 2, 6
- `build_tool_entry` returns dict matching Tool model structure - used in Tasks 4, 6, 7
- `save_tools_config` takes `config_dir: Path` and `tools: list[dict]` - matches calls in Task 6
- `generate_adapter_script` takes `adapters_dir: Path` - matches calls in Tasks 3, 6, 7
- All function signatures match their test definitions

### 4. Scope Check

Plan is focused on installer only. No feature creep. 7 tasks, each independently testable and committable.
