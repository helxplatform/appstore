# AppStore Overview

## Introduction
The HeLx Appstore is the primary user experience component of the HeLx data science platform. Through 
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
| bin/appstore image push          | Push the docker image to the repository.                     |
| bin/appstore image run {product} | Run automated unit tests with {product} settings.            |
| bin/appstore help                | Run automated unit tests with {product} settings.            |

## Testing
Automated testing uses the Python standard `unittest` and Django testing frameworks.
Tests should be fast enough to run conveniently, and maximize coverage. For example, the Django testing framework
allows for testing URL routes, middleware and other use interface elements in addition to the logic of components.

## Packaging
Appstore is packaged as a Docker image. It is a non-root container, meaning the user is not a superuser. It packages
a branch of Tycho cloned within the appstore hierarchy.

## Deployment
Appstore is deployed to Kubernetes in production using Helm. The main deployment concerns are:
**Security**: Secrets are added to the container via environment variables.
**Persistence**: Storage must be mounted for a database.
**Services**: The chief dependency is on Tycho which must be at the correct version.

## App Development
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
More information coming soon. The following script outlines the process:
```
#!/bin/bash

set -ex

# start fresh
rm -rf appstore
#  get a virtualenv
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
# clone appstore
if [ ! -d appstore ]; then
    git clone git@github.com:helxplatform/appstore.git
fi
cd appstore
# use metadata branch and install requirements
git checkout develop
cd appstore
pip install -r requirements.txt

# configure helx product => braini
product=braini
# configure dev mode to stub (run w/o tycho api)
export DEV_PHASE=stub
# create and or migrate the database
bin/appstore updatedb $product
# create the superuser (admin/admin by default)
bin/appstore createsuperuser
# execute automated tests
bin/appstore tests $product
# run the appstore at localhost:8000
bin/appstore run $product
```
### Development environment with Kubernetes

### Prerequisites:
- Have Access to a running k8s cluster.
- Have [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) set up.
- Create a .env file containing environment variables used by both Tycho and Appstore.
    ```
     export SECRET_KEY=""
   
   # Project specific settings. ( scidas | braini | cat | restartr | heal )
     export DJANGO_SETTINGS_MODULE="appstore.settings.<project>_settings"
     
   # Optional: Google or GitHub OAuth web app credentials.
     export OAUTH_PROVIDERS=""
     export GOOGLE_NAME=""
     export GOOGLE_CLIENT_ID=""
     export GOOGLE_SECRET=""
     
   # To skip the whitelisting step, add emails to authorize access to Appstore Home.
     export AUTHORIZED_USERS=""
   
   # Running Tycho in dev mode.
     export DEV_PHASE=dev
   
   # Namespace that Tycho launches Apps into on the cluster.
     export NAMESPACE=""
   
   # Default PVC used by Tycho.
     export stdnfsPvc="stdnfs"
   ```
   Install the environment variables in a terminal where Appstore and Tycho are cloned.
   ```
    source .env
   ```  
- Install Nginx and Ambassador in dev mode on the cluster in your namespace.

   A basic-values.yaml file that can be used for installing using the helm package manager.
   Instructions: https://github.com/helxplatform/devops/tree/develop#installing-the-chart
   
   ```
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

#### Installing kubectl on Linux:
- Download the latest release
    ```
    Run: curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"
    ```
- Make the kubectl binary executable:
    ```
     chmod +x ./kubectl
    ```
- Move the binary into your PATH:
    ```
    sudo mn ./kubectl /usr/local/bin/kubectl
    ```
- Check to see if installed:
    ```
    kubectl version --client
    ```
#### NOTE: 
   Once kubectl has been setup then set the KUBECONFIG env variable to use other kubeconfigs
 for example the one provided to you will be exported into the terminal where tycho api would be run: 
 export KUBECONFIG=path-to-kubeconfig-file.

### Step 1:

1. Clone the Appstore repo (develop branch):
    ```
     git clone -b develop [https://github.com/helxplatform/appstore.git](https://github.com/helxplatform/appstore.git)
    ```
2. Activate virtual environment: 
    ```
    python3 -m venv venv 

    source venv/bin/activate
   ```
3. Install the requirements: 
   
   NOTE: To work with Tycho and Appstore locally. Remove/Comment tycho-api==version dependency in 
   requirements.txt. Skip to Step 2. 
   ```
    pip install -r requirements.txt
   ```
4. Finally run Appstore by using the management CLI.
    
   ```
   bin/appstore start {product}
   ```
NOTE: After running bin/appstore start {product} for the first time, please use
bin/appstore run {product} every other time. So that migrations to the data-base will 
only take place once.

### Step 2:

1. Clone the Tycho repo (develop branch):
   ```
    git clone -b develop [https://github.com/helxplatform/tycho.git](https://github.com/helxplatform/tycho.git)
   ```
   Add cloned Tycho repo to the PYTHONPATH.
   ```
    PYTHONPATH=$PYTHONPATH:/path/to/the/tycho/project/root
   ```
2. Install the requirements:
   ```
    pip install -r requirements.txt
   ```
   Continue with Step-1 (Item 4)
### Step 3:
Now Appstore is running

If OAuth providers are not specified in the previous steps,

1. Navigate to the admin panel by appending /admin to the url : http://localhost:8000/admin.
2. Login in to the admin panel using admin/admin for user/password.
3. Nagivate to the application manager : http://localhost:8000/apps. From this endpoint we can launch applications.

If OAuth providers are provided in the previous steps,
1. Continue to login with google or github.
2. From here, can launch applications.

Since this is a development environment, the Appstore cannot redirect directly to the Apps after launching one.
There is unique URI generated for each pod with a pattern '/private/username/app-id/unique-sid'.
One way to find the unique URI is by describing the App pod service resource under annotations.

   ```
     kubectl describe svc <service-name> 
   ```
The app is then accessible at,

If server-name is specified while installing Nginx,

   ```
     http://<server-name>/unique-URI
   ```
If server-name is not specified while installing Nginx,
port-forward the Nginx service installed on the cluster works,
   ```
    kubectl port-forward service/<nginx-service> <host-port>/<container-port>
   ```
   ```
    http://localhost/unique-URI
   ```
 

