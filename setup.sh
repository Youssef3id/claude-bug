#!/usr/bin/env bash
# setup.sh — one-shot bootstrap for the bughunt workspace on a fresh box.
# Idempotent: safe to re-run.
#
# Usage:
#   ./setup.sh                            # auto-detect everything
#   ./setup.sh --corpus /path/to/data     # set corpus path explicitly
#   ./setup.sh --no-corpus                # skip corpus setup
set -euo pipefail

ROOT=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
CORPUS_PATH=""
SKIP_CORPUS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --corpus)    CORPUS_PATH="${2:-}"; shift 2 ;;
    --no-corpus) SKIP_CORPUS=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 1 ;;
  esac
done

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[1;33m!\033[0m %s\n' "$*"; }
fail() { printf '    \033[1;31m✗\033[0m %s\n' "$*"; exit 1; }

# ── 1. Prereqs ─────────────────────────────────────────────────────────────
say "Checking prerequisites"
missing=()
for bin in git python3 curl gzip zgrep bash; do
  if command -v "$bin" >/dev/null 2>&1; then
    ok "$bin: $(command -v "$bin")"
  else
    missing+=("$bin")
  fi
done
if [ ${#missing[@]} -gt 0 ]; then
  warn "missing: ${missing[*]}"
  if command -v apt-get >/dev/null 2>&1; then
    echo "    Install with: sudo apt-get update && sudo apt-get install -y ${missing[*]}"
  elif command -v dnf >/dev/null 2>&1; then
    echo "    Install with: sudo dnf install -y ${missing[*]}"
  elif command -v pacman >/dev/null 2>&1; then
    echo "    Install with: sudo pacman -S ${missing[*]}"
  fi
  fail "install the missing tools above and re-run."
fi

# ── 2. Make prowl executable + put it on PATH ──────────────────────────────
say "Installing prowl on PATH"
chmod +x "$ROOT/bin/prowl" "$ROOT/bin/_prowl_format.py"
ok "chmod +x bin/prowl"

mkdir -p "$HOME/.local/bin"
ln -sfn "$ROOT/bin/prowl" "$HOME/.local/bin/prowl"
ok "symlink: ~/.local/bin/prowl -> $ROOT/bin/prowl"

# Ensure ~/.local/bin is on PATH for future shells.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ok "~/.local/bin already on PATH" ;;
  *)
    SHELL_RC="$HOME/.bashrc"
    [ -n "${ZSH_VERSION:-}" ] && SHELL_RC="$HOME/.zshrc"
    if ! grep -q '\.local/bin' "$SHELL_RC" 2>/dev/null; then
      printf '\n# bughunt: prowl on PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$SHELL_RC"
      ok "added ~/.local/bin to PATH in $SHELL_RC"
      warn "open a new shell or run: source $SHELL_RC"
    else
      ok "$SHELL_RC already exports ~/.local/bin"
    fi
    ;;
esac

# Tell PROWL_ROOT where to find the workspace (for shells where ROOT != ~/bughunt).
if [ "$ROOT" != "$HOME/bughunt" ]; then
  warn "workspace is at $ROOT, not the default ~/bughunt"
  warn "export PROWL_ROOT=\"$ROOT\" in your shell rc, or use: PROWL_ROOT=$ROOT prowl <cmd>"
fi

# ── 3. Corpus (redscan dataset for `prowl lookup`) ─────────────────────────
say "Setting up corpus (redscan CVEs / writeups / methodology / CWEs)"
LINK="$ROOT/knowledge/corpus"

corpus_ok() {
  [ -d "$1" ] && [ -f "$1/cve.jsonl.gz" ] && [ -f "$1/writeup.jsonl.gz" ]
}

if [ "$SKIP_CORPUS" = "1" ]; then
  warn "skipping corpus setup (--no-corpus). prowl lookup will not work until you set PROWL_CORPUS."
elif [ -n "$CORPUS_PATH" ]; then
  if corpus_ok "$CORPUS_PATH"; then
    ln -sfn "$CORPUS_PATH" "$LINK"
    ok "corpus linked: $LINK -> $CORPUS_PATH"
  else
    fail "$CORPUS_PATH does not contain cve.jsonl.gz / writeup.jsonl.gz"
  fi
else
  # Already-valid symlink? Done.
  if [ -L "$LINK" ] && corpus_ok "$LINK"; then
    ok "corpus already linked: $LINK -> $(readlink "$LINK")"
  else
    # Auto-detect common locations.
    FOUND=""
    for cand in \
        "$HOME/redscan/data" \
        "$HOME/work/redscan/data" \
        "/mnt/c/Users/$USER/redscan/data" \
        "/opt/redscan/data" \
        "$ROOT/../redscan/data"; do
      if corpus_ok "$cand"; then FOUND="$cand"; break; fi
    done
    if [ -n "$FOUND" ]; then
      ln -sfn "$FOUND" "$LINK"
      ok "corpus auto-detected: $LINK -> $FOUND"
    else
      warn "redscan corpus not found. prowl lookup won't work until you fix this."
      warn "Options:"
      warn "  a) clone redscan, then re-run: ./setup.sh --corpus /path/to/redscan/data"
      warn "  b) per-shell: export PROWL_CORPUS=/path/to/redscan/data"
    fi
  fi
fi

# ── 4. Smoke tests ──────────────────────────────────────────────────────────
say "Smoke tests"
if PROWL_ROOT="$ROOT" "$ROOT/bin/prowl" list >/dev/null 2>&1; then
  ok "prowl list runs"
else
  warn "prowl list failed — investigate."
fi

if [ -L "$LINK" ] && corpus_ok "$LINK"; then
  if PROWL_ROOT="$ROOT" "$ROOT/bin/prowl" lookup "ssrf" -n 1 -t writeup >/dev/null 2>&1; then
    ok "prowl lookup runs (corpus reachable)"
  else
    warn "prowl lookup failed despite corpus link — check zgrep/python3"
  fi
else
  warn "prowl lookup not tested (corpus not configured)"
fi

# ── 5. Done ─────────────────────────────────────────────────────────────────
say "Done"
echo "Next steps:"
echo "  1. Open a new shell (or: source ~/.bashrc)"
echo "  2. prowl list                     # see all targets"
echo "  3. prowl hunt <host>              # resume hunting"
echo "  4. prowl lookup \"<query>\"         # search redscan corpus"
echo
echo "Workspace: $ROOT"
[ -L "$LINK" ] && echo "Corpus:    $LINK -> $(readlink "$LINK")"
