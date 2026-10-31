
pipeline {
    agent any

    environment {
        IMAGE = 'jeeva1304/employee-app:latest'
        CONTAINER = 'employee-web-app'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'docker build -t "$IMAGE" .'
            }
        }

        stage('Test') {
            steps {
                sh 'python3 -m compileall -q .'
            }
        }

        stage('Docker Login and Push') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'Dockerhub auth',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {
                    sh '''
                        set +x
                        echo "$DOCKER_PASS" | docker login \
                            -u "$DOCKER_USER" --password-stdin

                        docker push "$IMAGE"

                        docker logout
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    docker pull "$IMAGE"

                    docker rm -f "$CONTAINER" || true

                    docker run -d \
                        --name "$CONTAINER" \
                        --restart unless-stopped \
                        -p 5000:5000 \
                        "$IMAGE"
                '''
            }
        }
    }

    post {
        success {
            echo 'Employee Attendance Application Deployed!'
        }

        failure {
            echo 'Pipeline Failed!'
        }
    }
}
