#!/usr/bin/env bash
# Adapter for Qwen Code CLI
# Usage: bash qwen.sh --prompt "..." --cwd /path [--tool_id id]
set -euo pipefail

PROMPT=""
CWD=""
TOOL_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2 ;;
    --cwd)    CWD="$2";    shift 2 ;;
    --tool_id) TOOL_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Qwen-specific setup: PATH and config directories
export PATH="$HOME/.local/bin:$PATH"
export QWEN_CONFIG_DIR="${QWEN_CONFIG_DIR:-$HOME/.qwen}"
export QWEN_ACCOUNTS_DIR="${QWEN_ACCOUNTS_DIR:-$HOME/.qwen-accounts}"

# Execute Qwen Code
exec qwen --non-interactive --prompt "$PROMPT" --cwd "$CWD"
