#!/usr/bin/env bash
# lib/style/unix.sh — TTY-aware ANSI for dsweb (sourced).
# DS_COLOR=auto|always|never · NO_COLOR wins when auto.

DS_COLOR="${DS_COLOR:-auto}"

ds_style_enabled() {
  case "${DS_COLOR:-auto}" in
    always|1|true|yes|on) return 0 ;;
    never|0|false|no|off) return 1 ;;
    *)
      [[ -n "${NO_COLOR:-}" ]] && return 1
      [[ -t 2 ]] && return 0
      return 1
      ;;
  esac
}

ds_style_init() {
  if ds_style_enabled; then
    _S_RST=$'\033[0m'
    _S_BOLD=$'\033[1m'
    _S_DIM=$'\033[2m'
    _S_RED=$'\033[31m'
    _S_GRN=$'\033[32m'
    _S_YEL=$'\033[33m'
    _S_BLU=$'\033[34m'
    _S_MAG=$'\033[35m'
    _S_CYN=$'\033[36m'
    _S_MINT=$'\033[38;5;49m'
    _S_TEAL=$'\033[38;5;30m'
  else
    _S_RST=; _S_BOLD=; _S_DIM=
    _S_RED=; _S_GRN=; _S_YEL=; _S_BLU=; _S_MAG=; _S_CYN=
    _S_MINT=; _S_TEAL=
  fi
}

ds_style_init

ds_bold()  { printf '%s%s%s' "$_S_BOLD" "$*" "$_S_RST"; }
ds_dim()   { printf '%s%s%s' "$_S_DIM"  "$*" "$_S_RST"; }
ds_mint()  { printf '%s%s%s' "$_S_MINT" "$*" "$_S_RST"; }
ds_teal()  { printf '%s%s%s' "$_S_TEAL" "$*" "$_S_RST"; }

ds_hr() {
  local w="${1:-46}" out="${2:-2}"
  printf '%s' "$_S_DIM" >&"$out"
  printf '─%.0s' $(seq 1 "$w") >&"$out"
  printf '%s\n' "$_S_RST" >&"$out"
}

# ds_banner TITLE [lines...]  → stderr
ds_banner() {
  local title="$1"; shift || true
  printf '\n' >&2
  printf '  %s%s%s\n' "$_S_MINT$_S_BOLD" "$title" "$_S_RST" >&2
  ds_hr 46 2
  local line
  for line in "$@"; do
    printf '  %s\n' "$line" >&2
  done
  ds_hr 46 2
  printf '\n' >&2
}

# Help section header on stdout
ds_help_h() {
  printf '\n%s%s%s\n' "$_S_TEAL$_S_BOLD" "$1" "$_S_RST"
}

ds_help_line() {
  # ds_help_line <cmd> <desc>
  printf '  %s%-22s%s %s\n' "$_S_MINT" "$1" "$_S_RST" "$2"
}
