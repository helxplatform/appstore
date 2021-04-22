pipeline {
    agent { docker { image 'python:3.9.0-slim' } }
    stages {
        stage('Test') {
            steps {
                sh '''
                make test
                '''
            }
        }
        stage('Publish') {
            when {
                tag "release-*"
            }
            steps {
                sh '''
                make build
                make publish
                '''
            }
        }
    }
}