pipeline {
  agent {
    kubernetes {
        label 'kaniko-build-agent'
        yaml """
kind: Pod
metadata:
  name: kaniko
spec:
  containers:
  - name: jnlp
    workingDir: /home/jenkins/agent/
  - name: kaniko
    workingDir: /home/jenkins/agent/
    image: gcr.io/kaniko-project/executor:debug
    imagePullPolicy: Always
    resources:
      requests:
        cpu: "512m"
        memory: "1024Mi"
        ephemeral-storage: "4Gi"
      limits:
        cpu: "1024m"
        memory: "2048Mi"
        ephemeral-storage: "8Gi"
    command:
    - /busybox/cat
    tty: true
    volumeMounts:
    - name: jenkins-docker-cfg
      mountPath: /kaniko/.docker

  volumes:
  - name: jenkins-docker-cfg
    projected:
      sources:
      - secret:
          name: rencibuild-imagepull-secret
          items:
            - key: .dockerconfigjson
              path: config.json
"""
        }
    }
    stages {
        stage('Build') {
            environment {
                PATH="/busybox:/kaniko:$PATH"
                DOCKERHUB_CREDS=credentials("${env.REGISTRY_CREDS_ID_STR}")
                DOCKER_REGISTRY="${env.DOCKER_REGISTRY}"
                DOCKER_REPO="docker.io"
                DOCKER_OWNER="helxplatform"
                DOCKER_APP="appstore"

            }
            steps {
                container(name: 'kaniko', shell: '/busybox/sh') {
                    sh '''#!/busybox/sh
                        VERSION_FILE="appstore/appstore/_version.py"
                        VERSION=$(cut -d " " -f 3 "${VERSION_FILE}" | tr -d '"')
                        IMAGE_NAME=${DOCKER_OWNER}/${DOCKER_APP}:$VERSION
			echo "$IMAGE_NAME"
                        /kaniko/executor --dockerfile ./Dockerfile \
                                         --context . \
                                         --verbosity debug \
                                         --destination $IMAGE_NAME
                        '''
                }
            }
        }
        //stage('Test') {
        //    steps {
        //        container('agent-docker') {
        //            sh '''
        //            echo test
        //            '''
        //        }
        //    }
        //}
        //stage('Publish') {
        //    environment {
        //        DOCKERHUB_CREDS = credentials("${env.REGISTRY_CREDS_ID_STR}")
        //        DOCKER_REGISTRY = "${env.DOCKER_REGISTRY}"
        //    }
        //    steps {
        //        container('agent-docker') {
        //            sh '''
        //            echo publish
        //            echo $DOCKERHUB_CREDS_PSW | docker login -u $DOCKERHUB_CREDS_USR --password-stdin $DOCKER_REGISTRY
        //            docker push helxplatform/nginx:$BRANCH_NAME
        //            '''
        //        }
        //    }
        //}
    }
}
