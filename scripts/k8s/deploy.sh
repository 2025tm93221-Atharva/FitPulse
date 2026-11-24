#!/usr/bin/env bash
# Deploy <version> with one strategy or all of them; bootstraps an empty cluster.
. "$(dirname "$0")/lib.sh"
TARGET=${1:-}; VERSION=${2:-}; [ -n "$VERSION" ] || usage "<strategy|all> <version>"
DIR="$ROOT/scripts/k8s"

if ! k get deployment frontend >/dev/null 2>&1; then
  bash "$DIR/bootstrap.sh" "$VERSION"
fi
if [ "$TARGET" = all ]; then
  strategies="rolling blue-green canary shadow ab-testing"
else
  strategies=$TARGET
fi
for s in $strategies; do
  log "===== $s ====="
  bash "$DIR/$s.sh" deploy "$VERSION"
  # A/B, canary and shadow releases stay side by side until someone promotes them.
done
if [ "$TARGET" = all ]; then
  k set image deployment/frontend "nginx=$WEB_IMAGE:$VERSION"
  if ! wait_rollout frontend; then
    k rollout undo deployment/frontend
    wait_rollout frontend
    exit 1
  fi
fi
for s in $strategies; do echo "--- $s"; bash "$DIR/$s.sh" status; done
