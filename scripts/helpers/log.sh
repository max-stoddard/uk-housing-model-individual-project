#!/usr/bin/env bash
set -euo pipefail

# Shared logging helper for scripts. Usage:
#   source "scripts/helpers/log.sh"
#   LOG_TAG="WAS-VALID"
#   LOG_COLOR="\033[1;33m"
#   log_init
#   log "message"

LOG_COLOR_RESET="\033[0m"

log_init() {
  if [[ -t 1 ]]; then
    LOG_COLOR_ENABLED=true
  else
    LOG_COLOR_ENABLED=false
  fi
}

log_prefix() {
  if [[ "${LOG_COLOR_ENABLED:-false}" == "true" && -n "${LOG_COLOR:-}" ]]; then
    printf '[%b%s%b]' "${LOG_COLOR}" "${LOG_TAG}" "${LOG_COLOR_RESET}"
  else
    printf '[%s]' "${LOG_TAG}"
  fi
}

log() {
  if [[ -z "${LOG_TAG:-}" ]]; then
    printf '%s\n' "$*"
    return
  fi
  printf '%s %s\n' "$(log_prefix)" "$*"
}

log_err() {
  if [[ -z "${LOG_TAG:-}" ]]; then
    printf '%s\n' "$*" >&2
    return
  fi
  printf '%s %s\n' "$(log_prefix)" "$*" >&2
}
