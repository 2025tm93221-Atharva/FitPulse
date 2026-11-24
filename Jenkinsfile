// FitPulse: test -> quality gate -> images -> registry -> progressive delivery.
pipeline {
    agent any
    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }
    // Polls Git; a push is built within two minutes.
    triggers { pollSCM('H/2 * * * *') }
    parameters {
        choice(name: 'STRATEGY',
               choices: ['default', 'none', 'rolling', 'blue-green', 'canary', 'shadow', 'ab-testing', 'all'],
               description: 'Deployment strategy ("default" uses DEPLOY_STRATEGY from ci/.env)')
    }
    stages {
        stage('Prepare') {
            steps {
                script {
                    env.APP_VERSION = readFile('VERSION').trim()
                    def sha = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim()
                    // Immutable: the same tag is tested, pushed, deployed and rolled back to.
                    env.RELEASE = "${env.APP_VERSION}-b${env.BUILD_NUMBER}-${sha}"
                    env.TARGET = (params.STRATEGY ?: 'default') == 'default' ? (env.DEPLOY_STRATEGY ?: 'none') : params.STRATEGY
                    def prefix = env.DOCKERHUB_USER ? "docker.io/${env.DOCKERHUB_USER}/" : ''
                    env.API_IMAGE = "${prefix}fitpulse-api"
                    env.WEB_IMAGE = "${prefix}fitpulse-web"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} ${env.RELEASE}"
                }
                sh 'rm -rf reports dist-artifacts && mkdir -p reports dist-artifacts'
            }
        }
        stage('Build images') {
            steps {
                sh 'docker build --target test --build-arg APP_VERSION="$RELEASE" -t "$API_IMAGE:$RELEASE-test" backEnd'
                sh 'docker build --build-arg APP_VERSION="$RELEASE" -t "$API_IMAGE:$RELEASE" backEnd'
                sh 'docker build -t "$WEB_IMAGE:$RELEASE" frontEnd'
            }
        }
        stage('Pytest in container') {
            steps {
                // Copied out rather than mounted: the Docker daemon does not see Jenkins' filesystem.
                sh '''
                    name="fitpulse-test-$BUILD_NUMBER"
                    docker rm -f "$name" >/dev/null 2>&1 || true
                    rc=0
                    docker run --name "$name" "$API_IMAGE:$RELEASE-test" || rc=$?
                    docker cp "$name:/reports/." reports/ || true
                    docker rm -f "$name" >/dev/null
                    exit $rc
                '''
            }
            post { always { junit testResults: 'reports/junit.xml', allowEmptyResults: false } }
        }
        stage('SonarQube quality gate') {
            when { expression { return env.SONAR_HOST_URL } }
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    // qualitygate.wait fails this stage, and the build, when the gate is red.
                    sh '''
                        sed -i "s#<source>.*</source>#<source>/usr/src/backEnd/app</source>#" reports/coverage.xml
                        c=$(docker create --network fitpulse-ci -e SONAR_HOST_URL -e SONAR_TOKEN \
                            sonarsource/sonar-scanner-cli:latest \
                            -Dsonar.projectVersion="$APP_VERSION" \
                            -Dsonar.working.directory=/tmp/.scannerwork \
                            -Dsonar.qualitygate.wait=true -Dsonar.qualitygate.timeout=600)
                        trap 'docker rm -f "$c" >/dev/null' EXIT
                        docker cp . "$c:/usr/src"
                        docker start -a "$c"
                    '''
                }
            }
        }
        stage('Package artifacts') {
            steps {
                sh '''
                    git archive --format=tar.gz -o "dist-artifacts/fitpulse-$RELEASE.tar.gz" HEAD
                    bash -c '. scripts/k8s/lib.sh
                        for s in rolling blue-green canary shadow ab-testing frontend; do
                            render "k8s/$s" "$RELEASE" > "dist-artifacts/$s-$RELEASE.yaml"
                        done'
                    docker image inspect "$API_IMAGE:$RELEASE" "$WEB_IMAGE:$RELEASE" \
                        --format '{{index .RepoTags 0}} {{.Id}}' > "dist-artifacts/images-$RELEASE.txt"
                '''
            }
        }
        stage('Push to Docker Hub') {
            when { expression { return env.DOCKERHUB_USER } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'HUB_USER', passwordVariable: 'HUB_TOKEN')]) {
                    sh '''
                        export DOCKER_CONFIG=$(mktemp -d)
                        trap 'rm -rf "$DOCKER_CONFIG"' EXIT
                        echo "$HUB_TOKEN" | docker login -u "$HUB_USER" --password-stdin
                        for image in "$API_IMAGE" "$WEB_IMAGE"; do
                            docker push "$image:$RELEASE"
                            docker tag "$image:$RELEASE" "$image:$APP_VERSION"
                            docker push "$image:$APP_VERSION"
                        done
                    '''
                }
            }
        }
        stage('Load into Minikube') {
            when { expression { return !env.DOCKERHUB_USER && env.TARGET != 'none' } }
            steps { sh 'bash scripts/k8s/load-images.sh "$API_IMAGE:$RELEASE" "$WEB_IMAGE:$RELEASE"' }
        }
        stage('Deploy') {
            when { expression { return env.TARGET != 'none' } }
            steps { sh 'bash scripts/k8s/deploy.sh "$TARGET" "$RELEASE"' }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'reports/**,dist-artifacts/**', allowEmptyArchive: true, fingerprint: true
            sh 'docker image rm "$API_IMAGE:$RELEASE-test" >/dev/null 2>&1 || true'
        }
    }
}
