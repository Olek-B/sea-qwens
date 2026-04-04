# Sea Qwens Interactive Installer - Design Spec

**Date:** 2026-04-04
**Status:** Draft
**Author:** AI Assistant (brainstorming session with user)

---

## Overview

An interactive installer for Sea Qwens that guides users through tool configuration (with automatic Qwen Code profile detection), generates adapter scripts, and bootstraps the full Docker environment in one command.

**Command:** `./scripts/install.sh`

---

## Architecture

### Entry Point: `scripts/install.sh` (Bash)

Lightweight bash script that:
1. Checks prerequisites (Docker, Docker Compose, Python 3.11+, git)
2. Warns (non-fatal) if `qwen` CLI not found
3. Delegates to `python3 scripts/installer/main.py`

### Python Installer: `scripts/installer/`

```
scripts/installer/
├── __init__.py
├── main.py                 # Interactive wizard orchestrator
├── qwen_profiles.py        # Scan ~/.qwen-accounts, detect profiles
├── tools_config.py         # Generate tools.json entries
├── adapters.py             # Generate adapter scripts from templates
├── docker_check.py         # Verify Docker, Python, git + run compose
└── templates/
    └── adapter.sh.j2       # Jinja2 template for adapter scripts
```

No external dependencies beyond Python stdlib. Uses `input()` for prompts, color via ANSI escape codes.

---

## Installation Flow

### Phase 1: System Checks

```
[✓] Docker 20.10+ found
[✓] Docker Compose plugin found
[✓] Python 3.11.5 found
[✓] git 2.43.0 found
[!] Qwen Code not found (will be needed later)
```

Non-fatal warnings for missing optional deps. Fatal errors only for Docker/Python/git.

### Phase 2: Qwen Profile Detection

Scans `~/.qwen-accounts/` directory. Each subdirectory = one profile.

For each profile found, attempts to determine:
- **Display name** - from directory name (e.g., `adalovelace` → `Ada Lovelace` via title case, with special handling for known names like `mitchelbaker` → `Mitchel`)
- **OAuth status** - checks for `oauth_creds.json` in profile directory (present = active, missing = unknown)
- **Profile name** - the slug used with `qwen --profile <name>` (directory basename)

Interactive selection using numbered list:
```
Found 6 Qwen profiles in ~/.qwen-accounts:

  1. [✓] Ada (adalovelace)        - OAuth: active
  2. [✓] Turing (turing)          - OAuth: active
  3. [ ] Torwards (torwards)      - OAuth: unknown
  4. [✓] Mitchel (mitchelbaker)   - OAuth: active
  5. [ ] TwojaStara (twojastara)  - OAuth: active
  6. [ ] NieTwojaSprawa (nietwojasprawa) - OAuth: active

Enter profile numbers to enable (comma-separated, e.g. 1,2,4):
```

User enters `1,2,4` to enable Ada, Turing, Mitchel.

### Phase 3: Confirm Qwen Tools

Shows summary:
```
Will create 3 Qwen tools:
  • qwen-ada      → qwen --profile Ada --non-interactive
  • qwen-turing   → qwen --profile Turing --non-interactive
  • qwen-mitchel  → qwen --profile Mitchel --non-interactive

Add more Qwen profiles manually? [y/N]:
```

If yes, prompts for profile name and generates tool entry.

### Phase 4: Add Custom CLI Tools

```
Add other CLI tools (e.g. claude-code, aider, codex)? [y/N]:
```

If yes, loops:
```
Tool name: claude-code
CLI command: claude --no-interactive
Capabilities (comma-separated) [coding,testing,debugging]:
Capabilities: coding,testing,debugging,code-review

Add another tool? [y/N]:
```

Each custom tool generates:
- Entry in `tools.json` with name, command, capabilities
- Adapter script: `~/.config/sea-qwens/adapters/<toolname>.sh`

### Phase 5: Generate Configuration

```
Creating configuration...
  ✓ Created ~/.config/sea-qwens/
  ✓ Wrote tools.json (5 tools)
  ✓ Generated 5 adapter scripts
  ✓ Set permissions (chmod +x)
```

**tools.json structure per tool:**
```json
{
  "name": "qwen-ada",
  "command": "qwen --profile Ada --non-interactive",
  "adapter": "qwen-ada.sh",
  "usage_count": 0,
  "daily_limit": 1000,
  "capabilities": ["coding", "testing", "debugging", "refactoring"],
  "health_status": "HEALTHY",
  "consecutive_failures": 0,
  "requests_today": 0
}
```

**Adapter script structure (generated from template):**
```bash
#!/usr/bin/env bash
# Adapter for <tool_name>
set -euo pipefail
# ... argument parsing for --prompt, --cwd, --tool_id ...
exec <command> --prompt "$PROMPT" --cwd "$CWD"
```

For Qwen profiles, the command includes `--profile <Name>`.

### Phase 6: Docker Setup

```
Building Docker images...
  docker compose build

Starting services...
  ./scripts/start-sea-qwens.sh

Waiting for services to initialize (30s)...
```

Reuses existing `start-sea-qwens.sh` script.

### Phase 7: Verification

```
Verifying services...
  [✓] Librarian (http://localhost:8001) - healthy
  [✓] Atomizer  (http://localhost:8002) - healthy
  [✓] Kanban    (http://localhost:8003) - healthy
  [✓] Worker    (http://localhost:8004) - healthy
  [✓] Tester    (http://localhost:8005) - healthy

Loaded 5 tools into Neo4j:
  1. qwen-ada      [coding,testing,debugging,refactoring]
  2. qwen-turing   [coding,testing,debugging,refactoring]
  3. qwen-mitchel  [coding,testing,debugging,refactoring]
  4. claude-code   [coding,testing,debugging,code-review]
  5. ...

Installation complete! Next steps:
  1. Create a project: python -m services.manager.cli interview
  2. Or send a spec: curl -X POST http://localhost:8001/project-specs -d '{...}'
  3. Monitor services: docker compose logs -f
```

---

## Idempotency

Running the installer twice is safe:
- Existing tools in `tools.json` are shown with `[existing]` marker
- User can add new tools without duplicating existing ones
- Adapter scripts are only created if they don't exist
- Docker compose build/restart is safe to repeat

## Error Handling

- **Docker not found:** Fatal error with install instructions
- **Python < 3.11:** Fatal error
- **`~/.qwen-accounts` missing:** Skip Qwen profile phase, show info message
- **Librarian startup failure:** Retry 3 times with 10s delay, then show troubleshooting tips
- **Invalid input:** Re-prompt with explanation of expected format

## Cross-Platform Support

Config directory resolution reuses existing `shared/config.py`:
- Linux: `~/.config/sea-qwens/`
- macOS: `~/Library/Application Support/sea-qwens/`
- Windows: `%APPDATA%\sea-qwens\`

Qwen accounts directory: `~/.qwen-accounts/` (same on all platforms, configurable via `QWEN_ACCOUNTS_DIR` env var).

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `scripts/install.sh` | Bash entry point, system checks |
| `scripts/installer/__init__.py` | Package marker |
| `scripts/installer/main.py` | Interactive wizard |
| `scripts/installer/qwen_profiles.py` | Profile scanning |
| `scripts/installer/tools_config.py` | tools.json generation |
| `scripts/installer/adapters.py` | Adapter script generation |
| `scripts/installer/docker_check.py` | Docker verification + startup |
| `scripts/installer/templates/adapter.sh.j2` | Adapter template |

### Modified Files
| File | Change |
|------|--------|
| `configs/tools.json` | None - this is default template, installer generates user config |
| `README.md` | Add installer section with usage docs |

---

## Testing

Manual testing plan:
1. Run on clean system (no `~/.config/sea-qwens/`, no Qwen profiles)
2. Run with existing Qwen profiles
3. Run twice (idempotency)
4. Add custom tools
5. Verify Docker services start
6. Verify tools loaded into Neo4j
