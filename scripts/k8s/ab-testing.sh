#!/usr/bin/env bash
# A/B: sticky 50/50 split between group a (current) and group b (experiment).
. "$(dirname "$0")/lib.sh"
PORT=30085
experiment() { # on|off
  local rule="50% b;" sticky=b
  # Off must also move people who already hold a "b" cookie.
  [ "$1" = on ] || { rule=""; sticky=a; }
  k set env deployment/ab-gateway "B_RULE=$rule" "STICKY_B=$sticky"
  wait_rollout ab-gateway
}
case "${1:-}" in
  deploy)
    VERSION=${2:-}; [ -n "$VERSION" ] || usage "deploy <version>"
    migrate "$VERSION"
    experiment off
    set_version api-ab-b "$VERSION"
    if wait_rollout api-ab-b && smoke $PORT "$VERSION" "X-AB-Group: b"; then
      experiment on; log "experiment running: a=$(version_of api-ab-a) b=$VERSION"
    else
      log "variant b failed; everyone stays on a"
      set_version api-ab-b "$(version_of api-ab-a)"; exit 1
    fi ;;
  promote)
    set_version api-ab-a "$(version_of api-ab-b)"; wait_rollout api-ab-a; experiment off
    log "b won; everyone is on $(version_of api-ab-a)" ;;
  rollback) experiment off; set_version api-ab-b "$(version_of api-ab-a)"; log "experiment stopped" ;;
  status) echo "a=$(version_of api-ab-a) b=$(version_of api-ab-b)" ;;
  *) usage "deploy <version> | promote | rollback | status" ;;
esac
