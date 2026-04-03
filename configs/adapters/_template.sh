#!/usr/bin/env bash
# Template for new tool adapters
# Copy this file, rename it to <tool>.sh, and fill in the blanks.
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

# TODO: Set up tool-specific environment
# export PATH="/path/to/tool/bin:$PATH"
# export TOOL_CONFIG_DIR="$HOME/.tool-config"

# TODO: Execute the tool
# exec your-tool --non-interactive --prompt "$PROMPT" --cwd "$CWD"
echo "Adapter not configured" >&2
exit 1
