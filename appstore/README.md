# HeLx Overview

## Introduction
The HeLx Appstore is the primary user exeprience component of the HeLx data science platform. Through 
the appstore, users discover and interact with analytic tools and data to explore scientific problems.

## Use Cases
HeLx can be applied in many domains. It's ability to empower researchers to leverage advanced analytical tools
without installation or other infrastructure concerns has broad reaching benefits.

### BRAIN-I
BRAIN-I investigators create large images of brain tissue which are then visualized and analyzed using a variety of tools
which, architecturally, are not web applications but traditional desktop environments. These include image viewers like
ImageJ and Napari. Appstore presents these kinds of workspaces using CloudTop, a Linux desktop with screen sharing software and adapters for presenting
that interface via a web browser. CloudTop allows us to create HeLx apps for ImageJ, Napari, and other visualization tools.
These tools would be time consuming, complex, and error prone, for researchers to install and would still require them to
acquire the data. With CloudTop, the system can be run colocated with the data with no installation required.
### SciDAS
The Scientific Data Analysis at Scale project brings large scale computational workflow for research to cloud and on 
premise computing. Using the appstore, users are able to launch Nextflow API, a web based user interface to the
Nextflow workflow engine. Through that interface and associated tools, they are able to stage data into the system through
a variety of protocls, execute Nextflow workflows such as the GPU accelerated [KINK](https://github.com/SystemsGenetics/KINC)
workflow. Appstore and associated infrastructure has run KINK on the Google Kubernetes Engine and is being installed on the
[Nautilus Optiputer](https://nautilus.optiputer.net/).
### BioData Catalyst
NHLBI BioData Catalyst is a cloud-based platform providing tools, applications, and workflows in secure workspaces. The
RENCI team participating in the program uses HeLx as a development environment for new applications. It is the first host
for the team's DICOM medical imaging viewer. The system is designed to operate over 11TB of images in the cloud. We have
created versions using the OrthaNC DICOM server at the persistence layer as well as the Google Health Dicom API service.
HeLx also serves as the proving ground for concepts and demonstrations contributed to the BDC Apps and Tools Working Group. For
more information, see the [BioData Catalyst](https://biodatacatalyst.nhlbi.nih.gov/) website.
### Blackbalsam
Blackbalsam is an open source data science environment with an initial focus on COVID-19 and North Carolina. It
also serves as an experimental space for ideas and prototypes, some of which will graduate into the core of HeLx. For more
information, see the [blackbalsam documentation](https://github.com/stevencox/blackbalsam).
## Architecture
HeLx puts the most advanced analytical scientific models at investigator's finger tips using equally advanced cloud native,
container orchestrated, distributed computing systems.
### User Experience
Users browse tools of interest and launch those tools to explore and analyze available data. From the user's perspective,
HeLx will feel like an operating system since it runs useful tools. But there's no installation, the data's already
present in the cloud with the computation, and analyses can be reproducibly shared with others on the platform.

The appstore is a [Django](https://www.djangoproject.com/) based application whose chief responsibilities are authentication and authorization,
all visual presentation concerns including transtions between the appstore and apps.
### Compute
The system's underlying computational engine is Kubernetes. HeLx runs in a Kubernetes cluster and apps are launched and
managed within the same namespace, or administrative context, it uses. Tycho translates the docker compose representation
of systems with one ore more containers into a Kubernetes represenation, coordinates and tracks related processes, provides
utilization information on running processes, and manages the coordinated deletion of all components when a running application
is stopped.
### Storage
HeLx apps, in the near term, will mount a read only file system containing reference data and to a writable
file system for user data.
### Security
HeLx prefers open standard security protocols where available, and applies standards based best practices, especially from NIST
and FISMA, in several areas. 
#### Authentication
Authentication is concerned with verifying the identity of a principal and is distinct from determining what actions
tha principal is entitled to take in the system. We use the OpenID Connect (OIDC) protocol federate user identities 
from an OIDC identity provider (IdP) like Google or GitHub. The OIDC protocol is integrated into the system via open 
source connectors for the Django enviornment. This approach entails configuring the application within the platform of
each IdP to permit and execute the OIDC handshake.
#### Authorization
Authorization assumes an authenticated principal and is the determination of the actions permitted for that principal. The
first layer of authorization is a list of identities allowed access to the system. Email addresses associated with IdP
accounts are included in the list. Only principals whose IdPs present an email on the list on their behalf during authentication
are authorized to access the system.
#### Secrets
Data that serves, for example, as a credential for an authentication, must be secret. Since it may not be added to
source code control, these values are private to the deployment organization, and must be dynamically injected. 
This is handled by using Kubernetes secrets during deployment, and trivial keys for developer desktops, all 
within a uniform process framework. That framework provides a command line interface (CLI) for creating system 
super users, data migration, starting the application, and packaging executables, among other tasks.
#### Management CLI
The appstore management CLI provides uniform commands for using the environment. It provides default values for secrets
during local development and ways to provide secrets in proudction.
| Command                          |                   Description                                |
|:---------------------------------|:-------------------------------------------------------------|
|bin/appstore tests {product}      | Run automated unit tests with {product} settings.            |
|bin/appstore run {product}        | Run the appstore using {product} settings.                   |
|bin/appstore createsuperuser      | Create admin user with environment variable provided values. |
|bin/appstore image build          | Build the docker image.                                      |
|bin/appstore image push           | Push the docker image to the repository.                     |
|bin/appstore image run {product}  | Run automated unit tests with {product} settings.            |
|bin/appstore help                 | Run automated unit tests with {product} settings.            |

#### Testing
Automated testing uses the Python standard `unittest` and Django testing frameworks.
Tests should be fast enough to run conveniently, and maximize coverage. For example, the Django testing framework
allows for testing URL routes, middleware and other use interface elements in addition to the logic of components.
#### Packaging
Appstore is packaged as a Docker image. It is a non-root container, meaning the user is not a superuser. It packages
a branch of Tycho cloned within the appstore hierarchy.
#### Deployment
Appstore is deployed to Kubernetes in production using Helm. The main deployment concerns are:
**Security**: Secrets are added to the container via environment variables.
**Persistence**: Storage must be mounted for a datbaase.
**Services**: The chief dependency is on Tycho which must be at the correct version.
# App Development
During development, environment variables can be set to control execution:
| Variable                               |                   Description                                     |
|:---------------------------------------|:------------------------------------------------------------------|
|DEV_PHASE=[stub, local, dev, val, prod  | In stub, does not require a Tycho service.                        |
|ALLOW_DJANGO_LOGIN=[TRUE, FALSE]        | When true, presents username and password authentication options. |
|SECRET_KEY                              | Key for securing the application.                                 |
|OAUTH_PROVIDERS                         | Contains all the providers(google, github).                       |
|GOOGLE_CLIENT_ID                        | Contains the client_id of the provider.                           |         
|GOOGLE_SECRET                           | Contains the secret key for provider.                             |
|GOOGLE_NAME                             | Sets the name for the provider.                                   |
|GOOGLE_KEY                              | Holds the key value for provider.                                 |
|GOOGLE_SITES                            | Contains the sites for the provider.                              |   
|GITHUB_CLIENT_ID                        | Contains the client_id of the provider.                           |   
|GITHUB_SECRET                           | Contains the secret key of the provider.                          |
|GITHUB_NAME                             | Sets the name for the provider.                                   |
|GITHUB_KEY                              | Holds the key value for provider.                                 |
|GITHUB_SITES                            | Contains the sites for the provider.                              |
|APPSTORE_DJANGO_USERNAME                | Holds superuser username credentials.                             |
|APPSTORE_DJANGO_PASSWORD                | Holds superuser password credentials.                             |
|TYCHO_URL                               | Contains the url of the running tycho host.                       |
|OAUTH_DB_DIR                            | Contains the path for the database directory.                     |
|OAUTH_DB_FILE                           | Contains the path for the database file.                          |   
|POSTGRES_DB                             | Contains the connection of the database.                          |
|POSTGRES_HOST                           | Contains the database host.                                       | 
|DATABASE_USER                           | Contains the database username credentials.                       |
|DATABASE_PASSWORD                       | Contains the database password credentials.                       |
|APPSTORE_DEFAULT_FROM_EMAIL             | Default email address for appstore.                               | 
|APPSTORE_DEFAULT_SUPPORT_EMAIL          | Default support email for appstore.                               |
|ACCOUNT_DEFAULT_HTTP_PROTOCOL           | Allows to switch between http and https protocol.                 |

### App Metadata
Making application development easy is key to bringing the widest range of useful tools to the platform so we prefer
metadata to code wherever possible for creating HeLx Apps. Apps are systems of cooperating processes. These are expressed 
using [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/). Appstore uses
the [Tycho](https://helxplatform.github.io/tycho-docs/gen/html/index.html) engine to discover and manage Apps. The [Tycho app metadata](https://github.com/helxplatform/tycho/blob/metadata/tycho/conf/app-registry.yaml) format specifies the details of each application, contexts to which applications belong, and inheritance relationships between contexts.

Docker compose syntax is used to express cooperating containers comprising an application. The specificatinos are stored in [GitHub](https://github.com/helxplatform/app-support-prototype/tree/develop/dockstore-yaml-proposals), each in an application specific subfolder. Along with the docker compose, a `.env` file specifies environment variables for the application. If a file called icon.png is provided, that is used as the application's icon.
### Development Environment
More information coming soon. The following script outlines the process:
```
#!/bin/bash

set -ex

# start fresh
rm -rf appstore
#  get a vritualenv
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
git checkout metadata
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
# Next
HeLx is alpha. This sectionoutlines a few areas of anticipated focus for upcoming improvements.
## Architecture
### Semantic Search
Our team has a [semantic search](https://github.com/helxplatform/dug) engine for mapping to research data sets based on full text search. We anticipate extending the
Tycho metadata model to include semantic links to ontologies, incorporating analytical tools into the semantic search capability. See [EDAM](http://edamontology.org/page) & [Biolink](https://biolink.github.io/biolink-model/) for more information.
#### Utilization Metrics
Basic per application resource utilization information is already provided. But we anticipate creating scalable policy based resource management able to cope with the range of implications of the analytic workspaces we provide, ranging from single user notebooks, to GPU accelerated workflows, to Spark clusters.
### Proxy Management
HeLx uses software defined 
### Helm 3 Deployment
## Apps 
### Develop Verticals
#### Data Science [ Jupyter, RStudio, RShiny, Neo4J, ... ]
#### Artificial Intelligence [ Tensorflow, PyTorch, Keras, ... ]
#### Distributed Systems [ Spark, Kafka, Redis, ... ]
#### Workflow [ Nextflow, CWL, ... ]
#### Visualization [ Plotly/Dash, Leaflet, Seaborn, ... ] 
#### Medical Visualization [ CloudTop, Dicom, ... ]

