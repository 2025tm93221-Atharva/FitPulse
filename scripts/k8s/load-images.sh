#!/usr/bin/env bash
# Copy local images into the Minikube node (no registry needed).
set -euo pipefail
if docker exec minikube sh -c 'systemctl is-active -q docker'; then
  docker save "$@" | docker exec -i minikube docker load
else
  docker save "$@" | docker exec -i minikube ctr -n k8s.io images import -
fi
