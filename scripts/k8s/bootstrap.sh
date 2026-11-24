#!/usr/bin/env bash
# Create the namespace, secrets, database and all five strategies on <version>.
. "$(dirname "$0")/lib.sh"
VERSION=${1:-}; [ -n "$VERSION" ] || usage "<version>"

kubectl apply -f "$ROOT/k8s/base/namespace.yaml"
if ! k get secret fitpulse-secrets >/dev/null 2>&1; then
  log "generating fitpulse-secrets"
  pw=$(openssl rand -hex 24)
  url="postgresql+psycopg://fitness_app:$pw@postgres:5432"
  # From stdin rather than arguments, so values never appear in the process list.
  printf 'POSTGRES_PASSWORD=%s\nSECRET_KEY=%s\nDATABASE_URL=%s\nSHADOW_DATABASE_URL=%s\n' \
    "$pw" "$(openssl rand -hex 32)" "$url/fitness" "$url/fitness_shadow" |
    k create secret generic fitpulse-secrets --from-env-file=/dev/stdin
fi
kubectl apply -k "$ROOT/k8s/base"
k rollout status statefulset/postgres --timeout=180s
migrate "$VERSION"
migrate "$VERSION" SHADOW_DATABASE_URL

for strategy in rolling blue-green canary shadow ab-testing frontend; do
  log "creating $strategy"
  init "$strategy" "$VERSION"
  # One at a time: starting everything at once overloads a small node.
  for d in $(render "$ROOT/k8s/$strategy" "$VERSION" | kubectl get -f - -o name | grep '^deployment'); do
    k rollout status "$d" --timeout=240s
  done
done
k get deployments,services
