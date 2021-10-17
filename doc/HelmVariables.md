## Helm Configuration

The configuration variables that control the configuration of Appstore are transmitted from helm
and as part of helm creation, the following values are typical

appstore:
  image:
    repository: <imagename>
    tag: <branchname>
    pullPolicy: Always
  django:
    AUTHORIZED_USERS: <a list emails of authorized users>
    EMAIL_HOST_USER: "appstore@renci.org"
    EMAIL_HOST_PASSWORD: <secret>
    DOCKSTORE_APPS_BRANCH: <appstore branch>
    oauth:
      OAUTH_PROVIDERS: "github,google"
      GITHUB_NAME: <github name>
      GITHUB_CLIENT_ID: <github id>
      GITHUB_SECRET: <github secret>
      GOOGLE_NAME: <google name>
      GOOGLE_CLIENT_ID: <google client id>
      GOOGLE_SECRET: <google client secret>
  ACCOUNT_DEFAULT_HTTP_PROTOCOL: https
  appstoreEntrypointArgs: "make start"
  userStorage:
    createPVC: true
nfs-server:
  enabled: false
nginx:
  service:
    IP: <nginx ip>
    serverName: <appstore dns hostname>
  SSL:
    nginxTLSSecret: <tls secret>

### Parameters given by system administration

As part of user configuration, system administration will obtain the following

  - OAUTH_PROVIDERS
  - GITHUB_NAME
  - GITHUB_CLIENT_ID
  - GITHUB_SECRET
  - GOOGLE_NAME
  - GOOGLE_CLIENT_ID
  - GOOGLE_SECRET
  - serverName
  - IP
  - nginxTLSSecret
  - AUTHORIZED_USERS

### Typical configurable values

#### Image Name

- Parameter Name: repository

In the form of <username>/appstore and corresponds to the `docker push` used to push the
appstore image resulting from the build process.

#### Image Tag

- Parameter Name: tag

Also a parameter to the publiished image

#### Image Pull Rules

- Parameter Name: pullPolicy
- Typical Value: Always

A value of always guarantees that the image will be updated upon helm create if it is different than the
currently used one and is underpins the simple cycle push to docker, helm delete, follow by helm create

#### Dockstore Branch

- Parameter Name: DOCKSTORE_APPS_BRANCH

Indicates the branch contains the dockstore kubernetes app launch parameters
