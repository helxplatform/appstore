PYTHON       = /usr/bin/env python3
VERSION_FILE = ./appstore/appstore/_version.py
VERSION      = $(shell cut -d " " -f 3 ${VERSION_FILE})
DOCKER_REPO  = docker.io
DOCKER_OWNER = helxplatform
DOCKER_APP	 = appstore
DOCKER_TAG   = ${VERSION}
DOCKER_IMAGE = ${DOCKER_OWNER}/${DOCKER_APP}:$(DOCKER_TAG)
SECRET_KEY   = $(shell openssl rand -base64 12)
APP_LIST     ?= api appstore core frontend middleware product
BRANDS       = braini cat heal restartr scidas
SETTINGS_MODULE = ${DJANGO_SETTINGS_MODULE}


.DEFAULT_GOAL = help

.PHONY: help clean install test build image publish

#help: List available tasks on this project
help:
	@grep -E '^#[a-zA-Z\.\-]+:.*$$' $(MAKEFILE_LIST) | tr -d '#' | awk 'BEGIN {FS = ": "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

#build.image: Build the Docker image
build.image:
	echo "Building docker image: ${DOCKER_IMAGE}"
	docker pull helxplatform/helx-ui:latest
	docker build --no-cache --pull -t ${DOCKER_IMAGE} -f Dockerfile .
	echo "Successfully built: ${DOCKER_IMAGE}"

#build.image.test: Run test suite inside docker via compose
build.image.test:
	docker-compose -f docker-compose.test.yml up --build --exit-code-from appstore

# TODO, figure out how to patch tycho through to talk to the host kube from docker
# compose. Additionally because your local virtualenv may have the compose library
# installed by tycho the call to docker-compose may fail. Need to setup a venv check
# and message.

#build.python: Build wheel and source distribution packages
build.python:
	echo "Building distribution packages for version $(VERSION)"
	${PYTHON} -m pip install --upgrade build
	${PYTHON} -m build --sdist --wheel .
	echo "Successfully built version $(VERSION)"

#build: Build Python artifacts and Docker image
build: build.image

#appstore: Run the appstore application
appstore: appstore.brandcheck
	appstore runserver 0.0.0.0:8000 --settings=${SETTINGS_MODULE}

#appstore.collectstatic: Collect static assets from all installed Django apps
appstore.collectstatic:
	appstore collectstatic --settings=${SETTINGS_MODULE} --clear --no-input

#appstore.compose: Run the appstore via docker-compose
appstore.compose:
	docker-compose up --build

#appstore.frontend: Setup appstore frontend artifacts
appstore.frontend:
	docker pull helxplatform/helx-ui:latest
	docker run -d --name frontend helxplatform/helx-ui:latest;
	docker cp frontend:/usr/share/nginx/html/index.html ./appstore/frontend/templates/frontend;
	docker cp frontend:/usr/share/nginx/static/ ./appstore/frontend/;
	make frontend.cleanup

frontend.cleanup:
	docker container rm $(shell docker container stop $(shell docker container ls -q --filter name="frontend"))

#appstore.makemigrations: Setup database migrations for all installed Django apps
appstore.makemigrations:
	appstore makemigrations --settings=${SETTINGS_MODULE}

#appstore.migrate: Run database migrations for all installed Django apps
appstore.migrate:
	appstore migrate --settings=${SETTINGS_MODULE}

#appstore.openapi: Generate Open API schema
appstore.openapi:
	appstore spectacular --file ./appstore/schema.yml --settings=${SETTINGS_MODULE}

#appstore.setupsocialapps: Configure social login applications based on environment variables
appstore.setupsocialapps:
	appstore addingwhitelistedsocialapp --settings=${SETTINGS_MODULE}

#appstore.setupsuperuser: Configure Django super users
appstore.setupsuperuser:
	./bin/superuser.sh ${SETTINGS_MODULE}

#appstore.setupauthorizeduser: Configure users that are allowed to use the appstore
appstore.setupauthorizeduser:
	./bin/authorizeuser.sh ${SETTINGS_MODULE}

#appstore.run: Run the appstore application with gunicorn
appstore.run:
	gunicorn --bind 0.0.0.0:8000 --log-level=debug appstore.wsgi:application --workers=5

#appstore.brandcheck: Validation helper to confirm a brand setting has been provided
appstore.brandcheck:
	if [ -z ${SETTINGS_MODULE} ]; then make help && echo "\n\nPlease set the DJANGO_SETTINGS_MODULE environment variable\n\n"; exit 1; fi

#appstore.start: Helper to start the appstore application running all migrations and configuration before starting with gunicorn
appstore.start: appstore.brandcheck appstore.makemigrations appstore.migrate appstore.setupsocialapps appstore.setupsuperuser appstore.setupauthorizeduser appstore.collectstatic appstore.openapi appstore.run

#appstore.all: runs cleanup, install, test and starts the appstore
appstore.all: appstore.brandcheck clean install test appstore.start

#clean: Remove old build artifacts and installed packages
clean:
	${PYTHON} -m pip uninstall -y appstore
	${PYTHON} -m pip uninstall -y -r requirements.txt
	rm -rf appstore/static
	rm -rf build/
	rm -rf dist/
	rm -rf appstore/appstore.egg-info
	rm -f log/*.log
	rm -f appstore/DATABASE.sqlite3
	rm -f appstore/schema.yml
	rm -f tycho-registry.sqlite

#install: Install application along with required development packages
install:
	${PYTHON} -m pip install --upgrade pip
	${PYTHON} -m pip install -r requirements.txt
	${PYTHON} -m pip install -e .

# TODO if there is a way to turn this into a fully self contained package it 
# could be helpful for deployment and isolation, but that ends up impacting
# django INSTALLED_APPS and local django app development within a django 
# project. Changing `appstore/appstore` is the first step, but then django structure 
# and imports come into play. Can remove -e in pip install to start testing.

#Run flake8 on the source code
lint:
	${PYTHON} -m flake8 appstore

#test: Run all tests
test:
	$(foreach brand,$(BRANDS),SECRET_KEY=${SECRET_KEY} DEV_PHASE=stub appstore test $(APP_LIST) --settings=${SETTINGS_MODULE};)

# TODO look into using tox for testing multiple configurations and coverage integration

#all: Alias to clean, install, test, build, and image
all: appstore.brandcheck clean install test build

#publish.image: Push the Docker image
publish.image:
	docker tag ${DOCKER_IMAGE} ${DOCKER_REPO}/${DOCKER_IMAGE}
	docker push ${DOCKER_REPO}/${DOCKER_IMAGE}

#publish: Push all build artifacts to appropriate repositories
publish: publish.image