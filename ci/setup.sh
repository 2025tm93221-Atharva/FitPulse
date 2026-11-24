#!/usr/bin/env bash
# Prepare ci/.env and a kubeconfig that Jenkins can use from inside Docker.
set -euo pipefail
cd "$(dirname "$0")"
umask 077
mkdir -p .kube .empty
if [ ! -f .env ]; then
  sed "s/^JENKINS_ADMIN_PASSWORD=.*/JENKINS_ADMIN_PASSWORD=$(openssl rand -hex 16)/" .env.example > .env
fi
minikube kubectl -- config view --minify --flatten --context=minikube |
  sed -E 's#server: https://.*#server: https://minikube:8443#' > .kube/config
# Bind-mounted read-only into the Jenkins container, whose user is uid 1000.
chmod 755 .kube && chmod 644 .kube/config
echo "Edit ci/.env, then: docker compose -f ci/compose.yml --profile sonar up -d --build"
