pipeline {
    agent { dockerfile true  }
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