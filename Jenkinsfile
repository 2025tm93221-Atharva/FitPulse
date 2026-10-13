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
            tools {
                nodejs 'NodeJS 22'
            }
            steps {
                dir('frontEnd') {
                    sh '''
                        set -eu
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
                        poetry install --no-interaction --sync
                        ruff check --select E4,E7,E9,F app migrations tests
                        poetry run python -m compileall -q app migrations tests
                        poetry run pytest -q

                        migration_db="/tmp/fitpulse-jenkins-${BUILD_NUMBER}.db"
                        rm -f "$migration_db"
                        export DATABASE_URL="sqlite:////tmp/fitpulse-jenkins-${BUILD_NUMBER}.db"
                        poetry run alembic upgrade head
                        poetry run alembic check
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
