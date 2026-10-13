pipeline {
    agent {
        label 'fitpulse-ci'
    }

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 45, unit: 'MINUTES')
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
                        rm -f .jenkins-ci-migrations.db
                        DATABASE_URL="sqlite:////${WORKSPACE#/}/backEnd/.jenkins-ci-migrations.db" poetry run alembic upgrade head
                        DATABASE_URL="sqlite:////${WORKSPACE#/}/backEnd/.jenkins-ci-migrations.db" poetry run alembic check
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
                            docker build --pull -t "fitpulse-backend:${FITPULSE_IMAGE_TAG}" ./backEnd
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
}
