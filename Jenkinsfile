pipeline {
    agent {
        kubernetes {
            cloud 'kubernetes'
            label 'agent-docker'
            defaultContainer 'agent-docker'
        }
    }
    stages {
        stage('Install') {
            steps {
                sh '''
                make install
                '''
            }
        }
        stage('Test') {
            steps {
                sh '''
                make test
                '''
            }
        }
        stage('Publish') {
            when {
                anyOf {
                    branch 'develop'; buildingTag()
                }
            }
            environment {
                DOCKERHUB_CREDS = credentials(${env.REGISTRY_CREDS_ID_STR})
                DOCKER_REGISTRY = ${env.DOCKER_REGISTRY}
            }
            steps {
                sh '''
                echo $DOCKERHUB_CREDS_PSW | docker login -u $DOCKERHUB_CREDS_USR --password-stdin $DOCKER_REGISTRY
                make publish
                '''
            }
        }
    }
}