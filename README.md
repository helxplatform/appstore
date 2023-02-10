# AppStore Overview

## Introduction

The HeLx appstore is the primary user experience component of the HeLx data science
platform. Through the appstore, users discover and interact with analytic tools
and data to explore scientific problems.

## CLI

Using the provided `make` file you can `install` the appstore at which point it
will be setup for use via the `appstore` command, and the helper commands within
the root `Makefile`.

## Testing

Automated testing uses the Python standard `unittest` and Django testing frameworks.
Tests should be fast enough to run conveniently, and maximize coverage. For example,
the Django testing framework allows for testing URL routes, middleware and other
user interface elements in addition to the logic of components. Smoke and load
testing of the live server/API is implemented using the `artillery` npm package. 

## CI/CD

Github Actions are employed to lint, test, and build this project.

Linting Action:

Inline comments within the code such as `#noqa: F401` are necessary items that instruct the linter to bypass or perform a special action for specific sections of code. 
***DO NOT DELETE these inline comments.


## Packaging

Appstore is packaged as a Docker image. It is a non-root container, meaning the
user is not a superuser. It packages a frontend copied from [helx-ui](https://hub.docker.com/repository/docker/helxplatform/helx-ui).

### Releases

Following Semver, (major, minor, patch); containers will be tagged accordingly.

## Deployment

Appstore is deployed to Kubernetes in production using Helm. The main deployment
concerns are:

**Security**: Secrets are added to the container via environment variables.
**Persistence**: Storage must be mounted for a database.
**Services**: The chief dependency is on Tycho which must be at the correct version.

## Configuration Variables

During development, environment variables can be set to control execution:

| Variable                                    | Description                                                       |
| :-------------------------------------      | :---------------------------------------------------------------- |
| BRAND=[braini, cat, heal, restartr, scidas, eduhelx] | Product context configuration for the appstore.                   |
| DJANGO_SETTINGS_MODULE=[appstore.settings.<brand>_settings] | Product settings module configuration for the appstore.                   |
| DEV_PHASE=[stub, local, dev, val, prod]     | In stub, does not require a Tycho service.                        |
| ALLOW_DJANGO_LOGIN=[TRUE, FALSE]            | When true, presents username and password authentication options. |
| SECRET_KEY                                  | Key for securing the application.                                 |
| OAUTH_PROVIDERS                             | Contains all the providers(google, github).                       |
| GOOGLE_CLIENT_ID                            | Contains the client_id of the provider.                           |
| GOOGLE_SECRET                               | Contains the secret key for provider.                             |
| GOOGLE_NAME                                 | Sets the name for the provider.                                   |
| GITHUB_CLIENT_ID                            | Contains the client_id of the provider.                           |
| GITHUB_SECRET                               | Contains the secret key of the provider.                          |
| GITHUB_NAME                                 | Sets the name for the provider.                                   |
| APPSTORE_DJANGO_USERNAME                    | Holds superuser username credentials.                             |
| APPSTORE_DJANGO_PASSWORD                    | Holds superuser password credentials.                             |
| TYCHO_URL                                   | Contains the url of the running tycho host.                       |
| OAUTH_DB_DIR                                | Contains the path for the database directory.                     |
| OAUTH_DB_FILE                               | Contains the path for the database file.                          |
| APPSTORE_DEFAULT_FROM_EMAIL                 | Default email address for appstore.                               |
| APPSTORE_DEFAULT_SUPPORT_EMAIL              | Default support email for appstore.                               |
| ACCOUNT_DEFAULT_HTTP_PROTOCOL               | Allows to switch between http and https protocol.                 |

The provided .env.sample contains a starter that you can update and source for
development.

### App Metadata

Making application development easy is key to bringing the widest range of useful
tools to the platform so we prefer metadata to code wherever possible for creating
HeLx Apps. Apps are systems of cooperating processes. These are expressed using
[Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/).
Appstore uses the [Tycho](https://helxplatform.github.io/tycho-docs/gen/html/index.html)
engine to discover and manage Apps. The [Tycho app metadata](https://github.com/helxplatform/tycho/blob/metadata/tycho/conf/app-registry.yaml)
format specifies the details of each application, contexts to which applications
belong, and inheritance relationships between contexts.

Docker compose syntax is used to express cooperating containers comprising an application.
The specifications are stored in [GitHub](https://github.com/helxplatform/app-support-prototype/tree/develop/dockstore-yaml-proposals),
each in an application specific subfolder. Along with the docker compose, a `.env`
file specifies environment variables for the application. If a file called icon.png
is provided, that is used as the application's icon.

## Development Environment

### Prerequisites

- The appstore default database engine is postgresql. To setup a postgresql docker
container, the following steps are required.
```  
make build.postgresql
```

To use sqlite3 as the database backend,
```
export DEV_PHASE=local
```

- Some form of local kubernetes environment (minikube, kind, k3
etc).

### Local Development 

NOTE: You must run `make init` once you've cloned the repo to enable the commit-msg git hook so that conventional commits will apply automatically

#### With Tycho (default)

For local development you should have Python 3, a python virtual environment dedicated
to the project. You can configure your python environment with the following steps.

```bash
#!/bin/bash
set -ex

# start fresh
rm -rf appstore

# clone appstore
if [ ! -d appstore ]; then
    git clone git@github.com:helxplatform/appstore.git
fi
cd appstore

# make a virtualenv
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
git checkout develop
```

Install requirements

> NOTE: The below command will install requirements necessary for appstore which includes 
> Tycho pypi package, and it's requirements.
> Skip to [Cloning Tycho locally](#with-tycho-cloned-locally) to work on simultaneous changes to both projects.

```
make install
```

#### With Tycho cloned locally

> NOTE: To work with Tycho and appstore locally comment
> `tycho-api` in requirements.txt and setup.cfg.

Clone Tycho repo locally outside the appstore project.

```
git clone https://github.com/helxplatform/tycho.git
cd tycho
git checkout develop
```

Add Tycho folder to the PYTHON PATH. 

```
export PYTHONPATH=${PYTHONPATH}:/path/to/tycho/folder

Example:
export PYTHONPATH=$PYTHONPATH:/home/user/tycho
```

Install appstore and Tycho requirements
```
# To install appstore requirements
make install

# To install Tycho requirements
pip install -r /path/to/tycho/folder/requirements.txt

Example:
pip install -r /home/user/tycho/requirements.txt
```

You can use the commands packaged in `make` to configure and run the appstore. The below command is a way to
start appstore development server.

```bash
# configure environment variables, see above or .env.sample
export DEV_PHASE=stub
export SECRET_KEY=f00barBaz
# Runs database migrations, creates super user, runs test then runs the appstore
# at 0.0.0.0:8000
make start brand=braini
```

With appstore running, make the necessary changes (including Tycho if necessary). Next steps involve publishing the 
Tycho package to PyPI (Python Package Index). Jump to 
[Publishing the Tycho package](#coordination-of-development-for-tycho-and-appstore) for details.

#### Local testing with Artillery
To run Artillery tests locally, a few things need to be set up beforehand.

- Create test users in the DB (while starting the server). Once the test users have been created, they will persist until the database is wiped.
```bash
...
export CREATE_TEST_USERS=true
export TEST_USERS_PATH=artillery-tests/payloads
make start
```
- Configure environment variables for determining how the tests should run.
```bash
# The base URL of appstore, probably "http://localhost:8000" if running locally
export ARTILLERY_TARGET=<appstore_url>
# The type of tests to run. Smoke tests = 1 user; load tests = sustained load of many users 
export ARTILLERY_ENVIRONMENT=<smoke|load>
# * If running load tests, the following are also required. *
# The amount of users that "arrive" at the site per second during a load test.
export ARTILLERY_ARRIVAL_RATE=<users_per_second>
# The amount of seconds to run load testing for.
# Note: the total number of users created during a load test is ARTILLERY_ARRIVAL_RATE * ARTILLERY_DURATION
export ARTILLERY_DURATION=<seconds_to_run>
```
- Running the tests.
```bash
# The script will alert you if any required environment variables are missing.
make test.artillery
```

### Development environment with Kubernetes

#### Prerequisites

- Have Access to a running k8s cluster (local or remote).
- Have [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) set up.

> NOTE: Once kubectl has been setup then set the KUBECONFIG env variable to use
> other kubeconfigs for example the one provided to you will be exported into
> the terminal where tycho api would be run: export KUBECONFIG=path-to-kubeconfig-file.

### Kubernetes configuration

- Clone the `devops` repo that contains the `helx` helm charts

```bash
git clone git@github.com:helxplatform/devops.git
```

- Configure helm values

> A basic-values.yaml file that can be referenced along with additional details are
> available [here](https://github.com/helxplatform/devops/tree/develop#installing-the-chart).

A key part of your helm values if is the configuration of nginx and ambassador
if running locally the below settings should be enough. For non local environments
see the documentation in the note above at `helxplatform/devops`.

```bash
# Override the default values in the Nginx chart.
nginx:
  DEV_PHASE:
    dev: True
service:
  # Internal static IP for the Nginx service already assigned by admin.
  IP: 
  # Domain name already assigned by admin.
  serverName: 
```

- `helm` install the appstore:

```bash
helm install release-name $HELXPLATFORM_HOME/devops/helx --values basic-values.yaml --namespace your-k8s-namespace
```

> Note you can enable/disable services as part of your helm install values file.

You now have appstore and tycho running in a kubernetes environment ready for
testing. You can monitor pods/service status via `kubectl`.

### Artillery testing in Kubernetes
After helm installing Appstore, Artillery tests can be run using `helm test`.
The following chart values should be configured:
- Configure the `appstore` object according to the desired tests.
- Set `django.CREATE_TEST_USERS` to `true`.

If running load tests that last for extended durations (>5 minutes), tests should be run with a longer timeout condition e.g.:
```bash
helm test --timeout 30m
```
Since tests may run for extended periods of time, they can be monitored through the testing pod, e.g.:
```bash
kubectl logs appstore-artillery-test -f
```

### Manual OAuth provider setup

If OAuth providers are not specified in the previous steps,

1. Navigate to the admin panel by appending /admin to the url : http://localhost:8000/admin.
1. Login in to the admin panel using admin/admin for user/password.
1. Navigate to the application manager : http://localhost:8000/apps. From this
endpoint we can launch applications.

### Local Kubernetes service notes

Since this is a local development environment, the appstore cannot redirect directly
to the apps after launching one. There is unique URI generated for each pod with
the pattern '/private/username/app-id/unique-sid'. One way to find the unique URI
is by describing the app pod service resource under annotations.

```bash
kubectl describe svc <service-name> 
```

If you don't know the service name you can view all services with

```bash
kubectl get services
```

The app is then accessible at the prefix output path in the `describe` command
above.

### Local Kubernetes Nginx notes

If server-name is specified while installing Nginx,

```bash
http://<server-name>/unique-URI
```

If server-name is not specified while installing Nginx,
port-forward the Nginx service installed on the cluster works,

```bash
kubectl port-forward service/<nginx-service> <host-port>/<container-port>
```

Services should the be available at

```bash
http://localhost/unique-URI
```

### Frontend Development

The appstore has a new frontend being developed inside the [helx-ui](https://github.com/helxplatform/helx-ui)
that is served by Django. This frontend is focused on user interactions with
search and apps providing a rich experience while Django remains responsible
for authentication, authorization, routing and exposing data from Tycho.

This means that before a user is able to access the frontend `helx-ui` project
Django will provide a login page to authenticate the user, after which the
Django middleware will also make sure the user is allowed to access resources
as part of the authorization middleware. Once this is complete the user will be
able to navigate and interact with the new frontend which is served via the
`/frontend` Django app embedded in a Django view.

The new frontend is built in to the appstore docker image build. Inside of our
`Dockerfile` we use a multistage build to pull the frontend artifact out of the
`helx-ui` container into the `static` directory in the frontend Django app. That
artifact is then collected with `collectstatic` and served on the `/frontend`
route.

For local filesystem development `make appstore.frontend brand=cat` will pull the
`helx-ui` image, start the container, copy the artifacts to your local filesystem
in the frontend Django app, stop and remove the container. You can then run
`make appstore.start brand=cat` which will run database migrations, execute
`collectstatic` and start the appstore Django project for development and testing.

If changes need to happen to the frontend artifacts (react components, etc) those
changes will need to be done in the `helx-ui` repo which has instructions for
developing the frontend and testing appstore integration.


## Coordination of Development for Tycho and Appstore

>NOTE: Tycho is a library that provides a facility and API to manipulate launch and 
>get state information for kubernetes objects in a more simplistic manner.
>Appstore relies on this facility to launch apps as defined by an external 
>repository  and then later query/manager those objects afterwards.  Thus,
>Tycho is an Appstore dependency.  It's functionality is made available as
>a python package, and changes to tycho are accessed through an updated
>package.  During the development process this can be accomplished by either
>using a published package or using a locally created package.

### Install build support packages

    pip install setuptools==53.0.0
    pip install wheel==0.36.2
    pip install twine==3.3.0

### Publish a new tycho package

#### Create a pypi account and establish credentials

1. Log into pypi.org with credentials from helx-pypi-credentials.txt in Keybase
2. Go to Account Settings->API Tokens and generate a new token
  - don’t limit its scope to a new project
  - copy the token before you exit the screen
  - create a ~/.pypirc file with this content

    [pypi]
      username = __token__
      password = <pypi-token>

#### Publishing

This will build Tycho with your updates and publish a package to pypi.org

1.  Update version in /tycho.__init__.py

Use the  .dev* suffix for test versions

2. Publish from within the Tycho project folder.
```
python setup.py publish
```

#### Updating Appstore
 
1. Go to appstore code base and update tycho version in following files `requirements.txt`
and `setup.cfg` created in the publishing step

2. Build and publish appstore

## Cluster Kubernetes Config

Two files are provided, a kubeconfig which is used by helm and kubectl to define how
to connect to the BlackBalsam cluster, and a helm values yaml file (BB-values) used to override 
the default values established by a one time initialization described below.

### Github config

It's easier to just get a github oauth application set up, navigate to
`github->Settings->Developer Setting->OAuth Apps` and create a new OAuth App.
The name is arbitrary, but should have something to do with BlackBalsam and
Kubernetes as that's what it will authorize.  There needs to be a `homepage url`
and a `authorization callback url` set as follows.

    homepage url: https://helx.<your namespace>.blackbalsam-cluster.edc.renci.org/accounts/login
    authorization callback url: https://helx.<your namespace>.blackbalsam-cluster.edc.renci.org/accounts/github/login/callback/

Create the app, and add a secret.  The client id and secret need to be copied
into BB-values.

    GITHUB_CLIENT_ID: "<the client id>"
    GITHUB_SECRET: "<the secret>"

### Configuration using Helm

Value files should only contain those things which are not the default, to create the default values,
the following commands need to be run 1 time per namespace (usually there will only be 1 namespace).

That the top level directory of the devops repo, set the branch to develop

#### To obtain helm configs

    git clone git@github.com:helxplatform/devops.git

and then switch to the develop branch

    git checkout develop

and execute the following helm commands

    cd helx && helm dependency update && cd -
    cd helx/charts/dug && helm dependency update && cd -
    cd helx/charts/helx-monitoring && helm dependency update && cd -
    cd helx/charts/image-utils && helm dependency update && cd -
    cd helx/charts/roger && helm dependency update && cd -
    cd helx/charts/search && helm dependency update && cd -

followed up by the specializing config

    helm -n <namespace> upgrade --install helx devops/helx --values <BB-values>
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
