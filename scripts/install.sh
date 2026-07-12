#!/usr/bin/env bash
# Wire patternitty's capture hooks into a target project for Cursor/Copilot.
# Claude Code has a real install command (/plugin ...) so there's nothing to
# copy for it — this script only handles the two hosts that need files
# placed directly in the target repo.
set -euo pipefail

usage() { echo "usage: $(basename "$0") <target-project-dir> [cursor|copilot|all]"; exit 1; }

TARGET="${1:-}"; TOOL="${2:-all}"
[ -d "$TARGET" ] || usage
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

install_cursor() {
  mkdir -p "$TARGET/.cursor/rules"
  cp "$REPO_DIR/.cursor/rules/patternitty.mdc" "$TARGET/.cursor/rules/patternitty.mdc"
  if [ -f "$TARGET/.cursor/hooks.json" ]; then
    echo "skipped $TARGET/.cursor/hooks.json (already exists) — add this manually:"
    sed "s|<path-to-patternitty-clone>|$REPO_DIR|" "$REPO_DIR/.cursor/hooks.json"
  else
    sed "s|<path-to-patternitty-clone>|$REPO_DIR|" "$REPO_DIR/.cursor/hooks.json" > "$TARGET/.cursor/hooks.json"
    echo "wrote $TARGET/.cursor/hooks.json"
  fi
  echo "wrote $TARGET/.cursor/rules/patternitty.mdc"
}

install_copilot() {
  mkdir -p "$TARGET/.github/hooks"
  if [ -f "$TARGET/.github/hooks/patternitty-capture.json" ]; then
    echo "skipped $TARGET/.github/hooks/patternitty-capture.json (already exists)"
  else
    sed "s|<path-to-patternitty-clone>|$REPO_DIR|" "$REPO_DIR/.github/hooks/patternitty-capture.json" > "$TARGET/.github/hooks/patternitty-capture.json"
    echo "wrote $TARGET/.github/hooks/patternitty-capture.json"
  fi
  if [ -f "$TARGET/.github/copilot-instructions.md" ]; then
    echo "skipped $TARGET/.github/copilot-instructions.md (already exists) — append this manually:"
    cat "$REPO_DIR/.github/copilot-instructions.md"
  else
    cp "$REPO_DIR/.github/copilot-instructions.md" "$TARGET/.github/copilot-instructions.md"
    echo "wrote $TARGET/.github/copilot-instructions.md"
  fi
}

case "$TOOL" in
  cursor) install_cursor ;;
  copilot) install_copilot ;;
  all) install_cursor; install_copilot ;;
  *) usage ;;
esac
