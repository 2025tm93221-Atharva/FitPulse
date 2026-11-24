#!/usr/bin/env bash
# Blue-green: release to the idle colour, test it, then switch the live Service.
. "$(dirname "$0")/lib.sh"
LIVE_PORT=30082; PREVIEW_PORT=30086
live() { k get service bluegreen-live -o jsonpath='{.spec.selector.track}'; }
other() { if [ "$1" = blue ]; then echo green; else echo blue; fi; }
point() { k patch service "$1" -p "{\"spec\":{\"selector\":{\"track\":\"$2\"}}}"; }
switch_to() { point bluegreen-live "$1"; point bluegreen-preview "$(other "$1")"; }
# The Service switch takes a moment to reach kube-proxy.
settle() { sleep 3; }

case "${1:-}" in
  deploy)
    VERSION=${2:-}; [ -n "$VERSION" ] || usage "deploy <version>"
    OLD=$(live); NEW=$(other "$OLD")
    log "live=$OLD, releasing $VERSION to idle $NEW"
    migrate "$VERSION"
    point bluegreen-preview "$NEW"
    set_version "api-bluegreen-$NEW" "$VERSION"
    if ! { wait_rollout "api-bluegreen-$NEW" && settle && smoke $PREVIEW_PORT "$VERSION"; }; then
      log "$NEW failed before the switch; users are still on $OLD"
      exit 1
    fi
    switch_to "$NEW"; settle
    if ! smoke $LIVE_PORT "$VERSION"; then
      log "live check failed, switching back to $OLD"
      switch_to "$OLD"
      exit 1
    fi
    log "live is now $NEW ($VERSION); $OLD kept for instant rollback" ;;
  rollback)
    NEW=$(other "$(live)")
    wait_rollout "api-bluegreen-$NEW"   # never switch to an unhealthy colour
    switch_to "$NEW"
    log "live is now $NEW ($(version_of "api-bluegreen-$NEW"))" ;;
  status) echo "live=$(live) blue=$(version_of api-bluegreen-blue) green=$(version_of api-bluegreen-green)" ;;
  *) usage "deploy <version> | rollback | status" ;;
esac
