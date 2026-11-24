#!/usr/bin/env bash
# Shadow: mirror live requests to the new version; users only ever see stable.
. "$(dirname "$0")/lib.sh"
case "${1:-}" in
  deploy)
    VERSION=${2:-}; [ -n "$VERSION" ] || usage "deploy <version>"
    migrate "$VERSION" SHADOW_DATABASE_URL
    set_version api-shadow-shadow "$VERSION"
    if ! { wait_rollout api-shadow-shadow && smoke 30087 "$VERSION"; }; then
      log "shadow release failed; live traffic unaffected"
      set_version api-shadow-shadow "$(version_of api-shadow-stable)"
      exit 1
    fi
    log "shadow on $VERSION; compare with: $0 compare" ;;
  compare)
    for t in stable shadow; do
      # Probes are excluded: they hit each track independently of user traffic.
      echo "$t ($(version_of api-shadow-$t)) status counts:"
      k logs -l "strategy=shadow,track=$t" --tail=-1 --since="${2:-10m}" |
        grep -v 'kube-probe\|/api/health' | grep -oE 'HTTP/1.[01]" [0-9]{3}' | awk '{print $2}' | sort | uniq -c || true
    done ;;
  promote)
    VERSION=$(version_of api-shadow-shadow); OLD=$(version_of api-shadow-stable)
    migrate "$VERSION"
    set_version api-shadow-stable "$VERSION"
    wait_rollout api-shadow-stable || { set_version api-shadow-stable "$OLD"; exit 1; }
    log "stable is now $VERSION" ;;
  rollback) set_version api-shadow-shadow "$(version_of api-shadow-stable)"; wait_rollout api-shadow-shadow ;;
  status) echo "stable=$(version_of api-shadow-stable) shadow=$(version_of api-shadow-shadow)" ;;
  *) usage "deploy <version> | compare [since] | promote | rollback | status" ;;
esac
