#!/usr/bin/env bash
# Canary: send a growing share of requests to the new version, then promote or abort.
. "$(dirname "$0")/lib.sh"
PORT=30083
STEPS=${CANARY_STEPS:-"10 50"}
STEP_SECONDS=${CANARY_STEP_SECONDS:-20}

weight() {
  local rule=""
  [ "$1" = 0 ] || rule="$1% canary;"
  k set env deployment/canary-gateway "CANARY_RULE=$rule"
  wait_rollout canary-gateway
  log "canary weight is $1%"
}
abort() { log "aborting canary: $1"; weight 0; set_version api-canary-canary "$(version_of api-canary-stable)"; }
# Fails if canary pods restarted or any canary request answered 5xx.
healthy() {
  local restarts
  restarts=$(k get pods -l strategy=canary,track=canary -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}')
  for r in $restarts; do [ "$r" = 0 ] || return 1; done
  if k logs -l strategy=canary,track=canary --tail=-1 --since="${STEP_SECONDS}s" | grep -E '" 5[0-9][0-9]( |$)'; then
    return 1
  fi
}

case "${1:-}" in
  deploy)
    VERSION=${2:-}; [ -n "$VERSION" ] || usage "deploy <version>"
    migrate "$VERSION"
    weight 0
    set_version api-canary-canary "$VERSION"
    if ! { wait_rollout api-canary-canary && smoke $PORT "$VERSION" "X-Canary: always"; }; then
      abort "canary never became healthy"; exit 1
    fi
    for step in $STEPS; do
      weight "$step"; sleep "$STEP_SECONDS"
      healthy || { abort "errors at $step%"; exit 1; }
    done
    log "canary healthy; run promote or rollback" ;;
  promote)
    VERSION=$(version_of api-canary-canary); OLD=$(version_of api-canary-stable)
    set_version api-canary-stable "$VERSION"
    if ! wait_rollout api-canary-stable; then
      set_version api-canary-stable "$OLD"; abort "promotion failed"; exit 1
    fi
    weight 0
    log "stable is now $VERSION" ;;
  weight) weight "${2:?percent}" ;;
  rollback) abort "requested" ;;
  status) echo "stable=$(version_of api-canary-stable) canary=$(version_of api-canary-canary) rule='$(k get deployment canary-gateway -o jsonpath='{.spec.template.spec.containers[0].env[0].value}')'" ;;
  *) usage "deploy <version> | promote | rollback | weight <0-100> | status" ;;
esac
