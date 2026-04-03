#!/usr/bin/env bash
# Adapter for Qwen Code CLI
# Usage: bash qwen.sh --prompt "..." --cwd /path [--tool_id id]
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

# Qwen-specific setup: PATH and config directories
if [[ -n "${HOME:-}" && -d "$HOME/.local/bin" ]]; then
  export PATH="$HOME/.local/bin:$PATH"
fi
export QWEN_CONFIG_DIR="${QWEN_CONFIG_DIR:-$HOME/.qwen}"
export QWEN_ACCOUNTS_DIR="${QWEN_ACCOUNTS_DIR:-$HOME/.qwen-accounts}"

# Execute Qwen Code
# TOOL_ID is reserved for caller tracing; not passed to qwen
exec qwen --non-interactive --prompt "$PROMPT" --cwd "$CWD"
