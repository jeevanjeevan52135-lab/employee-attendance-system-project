pipeline {
    agent any

    environment {
        IMAGE = 'jeevan1304/employee-app'
    }

    stages {

        stage('Build') {
            steps {
                sh 'docker build -t $IMAGE .'
            }
        }

        stage('Test') {
            steps {
                sh 'python3 -m compileall -q .'
            }
        }

        stage('Docker Push') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {
                    sh '''
                        echo "$DOCKER_PASS" |
                        docker login -u "$DOCKER_USER" --password-stdin

                        docker push $IMAGE:$BUILD_NUMBER
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                 sh '''
                 docker rm -f employee-web-app || true
                 docker run -d --name employee-web-app -p 8000:5000 $IMAGE
            }
        }
    }
}