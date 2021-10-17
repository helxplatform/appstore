## Tycho for Appstore

Tycho is a library that provides a facility and API to manipulate launch and 
get state information for kubernetes objects in a more simplistic manner.
Appstor relies on this facility to launch apps as defined by an external 
repository  and then later query/manager those objects afterwards.  Thus,
Tycho is an Appstore dependency.  It's functionality is made available as
a python package, and changes to tycho are accessed through an updated
package.  During the development process this can be accomplished by either
using a published package or using a locally created package.

### Setting up the tycho repo for development

Following the gitflow workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow),
perform the following

    git clone git@github.com:helxplatform/tycho.git
    cd tycho
    git checkout develop
    git checkout -b <new feature-branch name>


### Install build support packages

    pip install setuptools==53.0.0
    pip install wheel==0.36.2
    pip install twine==3.3.0

### Method 1 Publish a new tycho package

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

This will build Tyco with your updates and publish a package to pypi.org

1.  Update version in /tycho.__init__.py

Use the  .dev* suffix for test versions

2. publish

    python setup.py publish

#### Updating Appstore
 
1. Go to appstore code base and update tycho version in following files `requirements.txt`
and `setup.cfg` created in the publishing step

2. build and publish appstore

### Method 2 Incorporate Local Tycho

1. Build a local .whl

    python setup.py bdist_wheel

2. Copy the .whl to appstore/whl

3. Copy .whl to appstore with altered `Dockerfile` `docker-compose.yml` and `requirements.txt`

- Add the following line to Dockerfile

    RUN pip install whl/*.whl

- alter docker-compose to produce an image named using a controlled tag

    image: <username>/appstore:<tag>

- Remove/Comment the tycho requirement from requirements.txt
