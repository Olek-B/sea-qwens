#!/usr/bin/env bash
# Template for new tool adapters
# Copy this file, rename it to <tool>.sh, and fill in the blanks.
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

# TODO: Set up tool-specific environment
# export PATH="/path/to/tool/bin:$PATH"
# export TOOL_CONFIG_DIR="$HOME/.tool-config"

# TODO: Execute the tool
# exec your-tool --non-interactive --prompt "$PROMPT" --cwd "$CWD"
echo "Adapter not configured" >&2
exit 1
