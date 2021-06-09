# AppStore Overview

## Introduction

The HeLx appstore is the primary user experience component of the HeLx data science platform. Through
the appstore, users discover and interact with analytic tools and data to explore scientific problems.

## Management CLI

The appstore management CLI provides uniform commands for using the environment. It provides default values for secrets
during local development and ways to provide secrets in production.
| Command                          | Description                                                  |
| :------------------------------- | :----------------------------------------------------------- |
| bin/appstore tests {product}     | Run automated unit tests with {product} settings.            |
| bin/appstore run {product}       | Run the appstore using {product} settings.                   |
| bin/appstore createsuperuser     | Create admin user with environment variable provided values. |
| bin/appstore image build         | Build the docker image.                                      |
| bin/appstore image frontend      | Pull frontend assets from helx-ui image for local dev.       |
| bin/appstore image push          | Push the docker image to the repository.                     |
| bin/appstore image run {product} | Run automated unit tests with {product} settings.            |
| bin/appstore help                | Run automated unit tests with {product} settings.            |

## Testing

Automated testing uses the Python standard `unittest` and Django testing frameworks.
Tests should be fast enough to run conveniently, and maximize coverage. For example, the Django testing framework
allows for testing URL routes, middleware and other use interface elements in addition to the logic of components.

## Packaging

Appstore is packaged as a Docker image. It is a non-root container, meaning the user is not a superuser. It packages
a frontend copied from [helx-ui](https://hub.docker.com/repository/docker/helxplatform/helx-ui).

## Deployment

Appstore is deployed to Kubernetes in production using Helm. The main deployment concerns are:
**Security**: Secrets are added to the container via environment variables.
**Persistence**: Storage must be mounted for a database.
**Services**: The chief dependency is on Tycho which must be at the correct version.

## Configuration Variables

During development, environment variables can be set to control execution:
| Variable                               | Description                                                       |
| :------------------------------------- | :---------------------------------------------------------------- |
| DEV_PHASE=[stub, local, dev, val, prod | In stub, does not require a Tycho service.                        |
| ALLOW_DJANGO_LOGIN=[TRUE, FALSE]       | When true, presents username and password authentication options. |
| SECRET_KEY                             | Key for securing the application.                                 |
| OAUTH_PROVIDERS                        | Contains all the providers(google, github).                       |
| GOOGLE_CLIENT_ID                       | Contains the client_id of the provider.                           |
| GOOGLE_SECRET                          | Contains the secret key for provider.                             |
| GOOGLE_NAME                            | Sets the name for the provider.                                   |
| GOOGLE_KEY                             | Holds the key value for provider.                                 |
| GOOGLE_SITES                           | Contains the sites for the provider.                              |
| GITHUB_CLIENT_ID                       | Contains the client_id of the provider.                           |
| GITHUB_SECRET                          | Contains the secret key of the provider.                          |
| GITHUB_NAME                            | Sets the name for the provider.                                   |
| GITHUB_KEY                             | Holds the key value for provider.                                 |
| GITHUB_SITES                           | Contains the sites for the provider.                              |
| APPSTORE_DJANGO_USERNAME               | Holds superuser username credentials.                             |
| APPSTORE_DJANGO_PASSWORD               | Holds superuser password credentials.                             |
| TYCHO_URL                              | Contains the url of the running tycho host.                       |
| OAUTH_DB_DIR                           | Contains the path for the database directory.                     |
| OAUTH_DB_FILE                          | Contains the path for the database file.                          |
| POSTGRES_DB                            | Contains the connection of the database.                          |
| POSTGRES_HOST                          | Contains the database host.                                       |
| DATABASE_USER                          | Contains the database username credentials.                       |
| DATABASE_PASSWORD                      | Contains the database password credentials.                       |
| APPSTORE_DEFAULT_FROM_EMAIL            | Default email address for appstore.                               |
| APPSTORE_DEFAULT_SUPPORT_EMAIL         | Default support email for appstore.                               |
| ACCOUNT_DEFAULT_HTTP_PROTOCOL          | Allows to switch between http and https protocol.                 |
| WHITELIST_REDIRECT                     | Toggle authorized user middleware to redirect or raise a 403.     |

### App Metadata

Making application development easy is key to bringing the widest range of useful tools to the platform so we prefer
metadata to code wherever possible for creating HeLx Apps. Apps are systems of cooperating processes. These are expressed
using [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/). Appstore uses
the [Tycho](https://helxplatform.github.io/tycho-docs/gen/html/index.html) engine to discover and manage Apps. The [Tycho app metadata](https://github.com/helxplatform/tycho/blob/metadata/tycho/conf/app-registry.yaml) format specifies the details of each application, contexts to which applications belong, and inheritance relationships between contexts.

Docker compose syntax is used to express cooperating containers comprising an application. The specifications are stored in [GitHub](https://github.com/helxplatform/app-support-prototype/tree/develop/dockstore-yaml-proposals), each in an application specific subfolder. Along with the docker compose, a `.env` file specifies environment variables for the application. If a file called icon.png is provided, that is used as the application's icon.

## Development Environment

### Local Development

For local development you should have Python 3, and some form of local kubernetes
environment (minikube, kind, k3 etc). You can configure your python environment with the
following steps.

```bash
#!/bin/bash

set -ex

# start fresh
rm -rf appstore
# get a virtualenv
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
# clone appstore
if [ ! -d appstore ]; then
    git clone git@github.com:helxplatform/appstore.git
fi
cd appstore
# use develop branch and install requirements
git checkout develop
cd appstore
pip install -r requirements.txt
```

You can use the commands packaged in `bin/appstore` to configure and run the
appstore.

```bash
# configure helx product => braini
product=braini
# configure dev mode to stub (run w/o tycho api)
export DEV_PHASE=stub
# setup local frontend assets
bin/appstore image frontend 
# Runs database migrations, creates super user, runs test then runs the appstore
# at localhost:8000
bin/appstore start $product
```

> NOTE: After running bin/appstore start {product} for the first time, use
> bin/appstore run {product} every other time so that migrations to the database
> will only run once.

For additional configuration options (`DEV_PHASE`, `product`, `OAUTH_PROVIDERS`)
inspect `bin/appstore` and `appstore/settings/*`.

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

### Kubernetes + local appstore configuration

With the helx chart installed in a local kubernetes environment you can run
appstore outside of `stub` mode and Tycho will launch services into your local
kubernetes cluster.

- Clone the appstore repo (develop branch)

```bash
git clone -b develop [https://github.com/helxplatform/appstore.git](https://github.com/helxplatform/appstore.git)
```

- Activate virtual environment

```bash
python3 -m venv venv 
source venv/bin/activate
```

- Install the requirements

> NOTE: To work with a custom Tycho version and appstore locally comment
> `tycho-api` in requirements.txt and add Tycho to your `PYTHON_PATH`. At this
> stage you should reference the Tycho note below then return to this step.

```bash
pip install -r requirements.txt
```

- Create a .env file containing environment variables used by both Tycho and appstore.

```text
export SECRET_KEY=<insert value>

# Project specific settings. (scidas | braini | cat | reccap | eduhelx)
export DJANGO_SETTINGS_MODULE="appstore.settings.<project>_settings"

# Optional: Google or GitHub OAuth web app credentials.
export OAUTH_PROVIDERS="github,google"
export GOOGLE_NAME=""
export GOOGLE_CLIENT_ID=""
export GOOGLE_SECRET=""
export GITHUB_NAME=""
export GITHUB_CLIENT_ID=""
export GITHUB_SECRET=""

# To skip the whitelisting step, add emails to authorize access to appstore home.
export AUTHORIZED_USERS=""

# Running Tycho in dev mode.
export DEV_PHASE=dev

# Namespace that Tycho launches Apps into on the cluster.
export NAMESPACE=""

# Default PVC used by Tycho.
export stdnfsPvc="stdnfs"
```

- Export the environment variables in a terminal where appstore and Tycho are cloned.

```bash
source .env
```

- Run appstore by using the `bin/appstore` management CLI.

```bash
bin/appstore image frontend 
bin/appstore updatedb $product
bin/appstore createsuperuser
bin/appstore tests $product
bin/appstore run $product
```

Appstore is now up and running. You should be able to see output from `gunicorn`
and `appstore`. Due to kubernetes running in a separate process space see the
notes below on viewing the apps that Tycho starts in your local Kubernetes
cluster.

### Developing with tycho locally

You may need to make changes to tycho and test them with the appstore. To do
this locally install tycho from a local repo clone with your changes instead
of the pypi version in the `appstore` requirements file.

- Clone the Tycho repo (develop branch):

```bash
git clone -b develop [https://github.com/helxplatform/tycho.git](https://github.com/helxplatform/tycho.git)
```

- Checkout you branch and make changes if required

```bash
git checkout -b <branch-name>
```

- Add cloned Tycho repo to the PYTHONPATH.

```bash
PYTHONPATH=$PYTHONPATH:/path/to/the/tycho/project/root
```

- Install the requirements:

```bash
pip install -r requirements.txt
```

- Return to appstore and continue setup.

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

For local filesystem development `bin/appstore image frontend` will pull the
`helx-ui` image, start the container, copy the artifacts to your local filesystem
in the frontend Django app, stop and remove the container. You can then run
`bin/appstore start $product` which will run database migrations, execute
`collectstatic` and start the appstore Django project for development and testing.

If changes need to happen to the frontend artifacts (react components, etc) those
changes will need to be done in the `helx-ui` repo which has instructions for
developing the frontend and testing appstore integration.
