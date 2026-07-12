#!/usr/bin/env bash
# One-time setup: make the personal pattern store its own git repo, the same
# way dotfiles are usually handled — local history from day one, a remote
# only if and when you decide to back it up.
set -euo pipefail

HOME_DIR="${PATTERNITTY_HOME:-$HOME/.patternitty}"
STORE="$HOME_DIR/patterns"
mkdir -p "$STORE"

# ponytail: the store self-initializes on first write (see _lib.ensure_store);
# this script is just the explicit-setup convenience. No index files to seed —
# index.json/index.html are derived by compile.py/dashboard.
if [ ! -d "$HOME_DIR/.git" ]; then
  git -C "$HOME_DIR" init -q
  git -C "$HOME_DIR" add -A
  git -C "$HOME_DIR" commit -q -m "patternitty: initialize pattern store"
  echo "initialized git repo at $HOME_DIR"
else
  echo "$HOME_DIR is already a git repo"
fi

cat <<EOF

To back this up (optional, never done automatically):
  gh repo create <you>/patterns --private --source "$HOME_DIR" --remote origin --push
EOF
