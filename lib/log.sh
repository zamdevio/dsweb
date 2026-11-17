#!/usr/bin/env bash
# lib/log.sh — styled logger. Sourced only.

# shellcheck source=style/unix.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/style/unix.sh"

# Compact channel tags: ds · + msg
_log_tag() {
  # $1=color $2=glyph
  printf '%sds%s %s%s%s ' "$_S_DIM" "$_S_RST" "$1$_S_BOLD" "$2" "$_S_RST"
}

log_info()  { _log_tag "$_S_CYN" "·"; printf '%s\n' "$*" >&2; }
log_ok()    { _log_tag "$_S_GRN" "+"; printf '%s\n' "$*" >&2; }
log_warn()  { _log_tag "$_S_YEL" "!"; printf '%s\n' "$*" >&2; }
log_err()   { _log_tag "$_S_RED" "x"; printf '%s\n' "$*" >&2; }
log_debug() {
  [[ -n ${DS_DEBUG:-} ]] || return 0
  _log_tag "$_S_DIM" "?"; printf '%s\n' "$*" >&2
}

# Key / value aligned row (stderr)
log_kv() {
  printf '  %s%-12s%s %s\n' "$_S_DIM" "$1" "$_S_RST" "$2" >&2
}

die() { log_err "$*"; exit 1; }
