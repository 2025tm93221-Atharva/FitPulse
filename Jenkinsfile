pipeline { 

 

    agent any 

 

    triggers { 

        pollSCM('H/2 * * * *') 

    } 

 

    stages { 

 

        stage('Checkout') { 

            steps { 

                echo 'Checking out source code' 

                checkout scm 

            } 

        } 

 

        stage('Build') { 

            steps { 

                echo 'Installing Python dependencies' 

 

                sh ''' 

                    python3 -m venv .venv 

                    .venv/bin/pip install -r requirements.txt 

                ''' 

            } 

        } 

 

        stage('Test') { 

            steps { 

                echo 'Running automated tests' 

 

                sh ''' 

                    .venv/bin/pytest -q 

                ''' 

            } 

        } 

 

        stage('Code Inspection') { 

            steps { 

                echo 'Running SonarQube analysis' 

 

                sh ''' 

                    sonar-scanner 

                ''' 

            } 

        } 

 

        stage('Deploy') { 

            steps { 

                echo 'Deploying application' 

 

                sh ''' 

                    mkdir -p /tmp/student-task-manager 

 

                    cp -r app.py templates static requirements.txt \ 

                        /tmp/student-task-manager/ 

 

                    cd /tmp/student-task-manager 

 

                    python3 -m venv .venv 

 

                    .venv/bin/pip install -r requirements.txt 

 

                    if [ -f app.pid ]; then 

                        kill $(cat app.pid) 2>/dev/null || true 

                    fi 

 

                    nohup .venv/bin/python app.py \ 

                        > app.log 2>&1 & 

 

                    echo $! > app.pid 

                ''' 

            } 

        } 

 

    } 

 

    post { 

 

        success { 

            echo 'CI/CD pipeline completed successfully' 

        } 

 

        failure { 

            echo 'Pipeline failed - deployment was not completed' 

        } 

 

    } 

} 