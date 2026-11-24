#!/usr/bin/env bash
# Rolling update. A failed rollout or smoke test rolls back automatically.
. "$(dirname "$0")/lib.sh"
D=api-rolling; PORT=30081
case "${1:-}" in
  deploy)
    VERSION=${2:-}; [ -n "$VERSION" ] || usage "deploy <version>"
    OLD=$(version_of $D)
    migrate "$VERSION"
    set_version $D "$VERSION"
    k annotate "deployment/$D" "kubernetes.io/change-cause=release $VERSION" --overwrite
    if wait_rollout $D && smoke $PORT "$VERSION"; then
      log "rolling update to $VERSION complete"
    else
      log "release $VERSION failed, rolling back to $OLD"
      # Explicit version, so this also works when the failed release was a re-deploy.
      set_version $D "$OLD"
      wait_rollout $D
      exit 1
    fi ;;
  rollback) k rollout undo "deployment/$D"; wait_rollout $D; log "now on $(version_of $D)" ;;
  status) k rollout history "deployment/$D"; version_of $D ;;
  *) usage "deploy <version> | rollback | status" ;;
esac
