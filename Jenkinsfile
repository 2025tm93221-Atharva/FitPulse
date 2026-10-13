pipeline {
    agent any
  

    triggers {
        pollSCM('H/5 * * * *')
    }

    stages {
        stage('Clean checkout') {
            steps {
                deleteDir()
                checkout scm
            }
        }

        stage('Frontend quality gate') {
            steps {
                dir('frontEnd') {
                    sh '''
                        set -eu
                        if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
                            echo 'Node.js 22 and npm must be installed on the Jenkins agent and available on PATH.'
                            exit 1
                        fi
                        node_major="$(node -p 'process.versions.node.split(".")[0]')"
                        if [ "$node_major" != "22" ]; then
                            echo "Node.js 22 is required; found $(node --version)."
                            exit 1
                        fi
                        node --version
                        npm --version
                        npm ci
                        npm run lint
                        npm test
                        npm run build
                    '''
                }
            }
        }

        stage('Backend quality gate') {
            steps {
                dir('backEnd') {
                    sh '''
                        set -eu
                        python3.14 -m venv .venv
                        .venv/bin/python -m pip install --upgrade pip
                        .venv/bin/python -m pip install -r requirements.txt ruff==0.17.0
                        export PATH="$PWD/.venv/bin:$PATH"
                        ruff check --select E4,E7,E9,F app migrations tests
                        python -m compileall -q app migrations tests
                        pytest -q

                        migration_db="/tmp/fitpulse-jenkins-${BUILD_NUMBER}.db"
                        rm -f "$migration_db"
                        export DATABASE_URL="sqlite:////tmp/fitpulse-jenkins-${BUILD_NUMBER}.db"
                        alembic upgrade head
                        alembic check
                    '''
                }
            }
        }

        stage('Docker image builds') {
            steps {
                script {
                    def imageTag = "jenkins-${env.BUILD_TAG.replaceAll(/[^A-Za-z0-9_.-]/, '-').take(100)}"
                    withEnv(["FITPULSE_IMAGE_TAG=${imageTag}"]) {
                        sh '''
                            set -eu
                            docker build --pull \
                                -t "fitpulse-backend:${FITPULSE_IMAGE_TAG}" \
                                ./backEnd
                            docker build --pull \
                                --build-arg VITE_API_BASE_URL= \
                                -t "fitpulse-frontend:${FITPULSE_IMAGE_TAG}" \
                                ./frontEnd
                        '''
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'FitPulse quality gates and Docker image builds completed successfully.'
        }
        failure {
            echo 'FitPulse CI failed. Review the stage logs; no deployment was attempted.'
        }
    }
}
