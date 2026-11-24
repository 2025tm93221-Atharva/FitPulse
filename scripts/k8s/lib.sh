# Shared helpers; sourced by the deployment scripts.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
NS=fitpulse
# Image names; set e.g. API_IMAGE=docker.io/<dockerhub-user>/fitpulse-api for a registry.
API_IMAGE=${API_IMAGE:-fitpulse-api}
WEB_IMAGE=${WEB_IMAGE:-fitpulse-web}
# Where smoke tests reach NodePorts (default: from a container on Minikube's network).
SMOKE_HOST=${SMOKE_HOST:-minikube}
SMOKE_NETWORK=${SMOKE_NETWORK:-minikube}
ROLLOUT_TIMEOUT=${ROLLOUT_TIMEOUT:-120s}

log() { echo ">> $*"; }
k() { kubectl -n "$NS" "$@"; }

# render <kustomize dir or file> <version>: substitute image names and version.
render() {
  if [ -d "$1" ]; then kubectl kustomize "$1"; else cat "$1"; fi |
    sed -e "s#image: fitpulse-api:APP_VERSION#image: $API_IMAGE:$2#" \
        -e "s#image: fitpulse-web:APP_VERSION#image: $WEB_IMAGE:$2#"
}

# First-time creation only; later releases change images so live state is not reset.
init() { # <strategy dir> <version>
  render "$ROOT/k8s/$1" "$2" | kubectl apply -f -
}

wait_rollout() { k rollout status "deployment/$1" --timeout="$ROLLOUT_TIMEOUT"; }
set_version() { k set image "deployment/$1" "api=$API_IMAGE:$2"; }
image_of() { k get deployment "$1" -o jsonpath='{.spec.template.spec.containers[0].image}'; }
version_of() { local i; i=$(image_of "$1"); echo "${i##*:}"; }

migrate() { # <version> [secret key]
  local key=${2:-DATABASE_URL} job
  # The time suffix keeps reruns of one version from colliding.
  job="migrate-$(echo "$1" | tr '.+_' '---' | tr 'A-Z' 'a-z')-$(date +%s)"
  log "migrating ($key) with $1"
  render "$ROOT/k8s/base/migrate-job.yaml" "$1" |
    sed -e "s/JOB_NAME/$job/" -e "s/DB_KEY/$key/" | kubectl apply -f -
  if ! k wait --for=condition=complete "job/$job" --timeout="$ROLLOUT_TIMEOUT"; then
    k logs "job/$job" --tail=50 || true
    return 1
  fi
}

# Post-deployment pytest, run inside the release's own test image.
smoke() { # <node port> <expected version> [extra header]
  log "smoke test on port $1, expecting $2"
  docker run --rm --network "$SMOKE_NETWORK" \
    -e BASE_URL="http://$SMOKE_HOST:$1" -e EXPECT_VERSION="$2" -e EXTRA_HEADER="${3:-}" \
    "$API_IMAGE:$2-test" pytest -q -p no:cacheprovider smoke
}

usage() { echo "usage: $0 $*" >&2; exit 2; }
