# FitPulse

Gym membership platform: FastAPI backend, React frontend, PostgreSQL, with a Jenkins CI/CD
pipeline and five Kubernetes deployment strategies.

## Run the tests

```bash
docker build --target test -t fitpulse-api:test backEnd && docker run --rm fitpulse-api:test
```

## Cluster

Needs Docker, kubectl, Minikube and about 4 GB of RAM for Docker.

```bash
minikube start --driver=docker --cpus=4 --memory=3300mb --ports=30080:30080,30081:30081,30082:30082,30083:30083,30084:30084,30085:30085
V=$(cat VERSION)
docker build --target test --build-arg APP_VERSION=$V -t fitpulse-api:$V-test backEnd
docker build --build-arg APP_VERSION=$V -t fitpulse-api:$V backEnd
docker build -t fitpulse-web:$V frontEnd
scripts/k8s/load-images.sh fitpulse-api:$V fitpulse-web:$V
scripts/k8s/bootstrap.sh $V
```

| Strategy | Endpoint | Commands |
| --- | --- | --- |
| Frontend | http://localhost:30080 | |
| Rolling | http://localhost:30081/api/version | `scripts/k8s/rolling.sh deploy V`, `rollback` |
| Blue-green | http://localhost:30082/api/version | `scripts/k8s/blue-green.sh deploy V`, `rollback` |
| Canary | http://localhost:30083/api/version | `scripts/k8s/canary.sh deploy V`, `promote`, `rollback` |
| Shadow | http://localhost:30084/api/version | `scripts/k8s/shadow.sh deploy V`, `compare`, `promote`, `rollback` |
| A/B | http://localhost:30085/api/version | `scripts/k8s/ab-testing.sh deploy V`, `promote`, `rollback` |

`scripts/k8s/load.py URL` measures dropped requests and the version split during a release.
Migrations run before each release and must stay compatible with the previous version,
because rollback changes the image and not the schema.

## Jenkins, SonarQube and Docker Hub

```bash
ci/setup.sh
docker compose -f ci/compose.yml --profile sonar up -d --build
```

- Jenkins: http://localhost:8090 (user `admin`, password in `ci/.env`)
- SonarQube: http://localhost:9000. Create a token, then set `SONAR_TOKEN` and
  `SONAR_HOST_URL=http://sonarqube:9000` in `ci/.env` and rerun the compose command.
- Docker Hub: set `DOCKERHUB_USER` and `DOCKERHUB_TOKEN` in `ci/.env`. While empty, the push
  stage is skipped and images are loaded straight into Minikube.

With little RAM, run SonarQube with Minikube stopped and `DEPLOY_STRATEGY=none`.
