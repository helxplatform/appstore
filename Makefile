PYTHON          := /usr/bin/env python3
VERSION_FILE    := ./appstore/appstore/_version.py
VERSION         := $(shell grep __version__ ${VERSION_FILE} | cut -d " " -f 3 ${VERSION_FILE} | tr -d '"')
COMMIT_HASH     := $(shell git rev-parse --short HEAD)

# If env defines a registry, use it, else use the default
DEFAULT_REGISTRY := docker.io
ifdef DOCKER_REGISTRY
ifeq "$(origin DOCKER_REGISTRY)" "environment"
DOCKER_REGISTRY := ${DOCKER_REGISTRY}
else
DOCKER_REGISTRY := ${DEFAULT_REGISTRY}
endif
else
DOCKER_REGISTRY := ${DEFAULT_REGISTRY}
endif

DOCKER_OWNER    := frostyfan109
DOCKER_APP      := appstore
DOCKER_TAG      := 1.3.dev5
DOCKER_IMAGE    := ${DOCKER_OWNER}/${DOCKER_APP}:$(DOCKER_TAG)
SECRET_KEY      := $(shell openssl rand -base64 12)
APP_LIST        ?= api appstore core frontend middleware product
BRANDS          := braini cat heal restartr scidas eduhelx argus
MANAGE	        := ${PYTHON} appstore/manage.py
SETTINGS_MODULE := ${DJANGO_SETTINGS_MODULE}
ARTILLERY_ENV   := ${ARTILLERY_ENVIRONMENT}
ARTILLERY_TARGET:= ${ARTILLERY_TARGET}

ifdef GUNICORN_WORKERS
NO_OF_GUNICORN_WORKERS := $(GUNICORN_WORKERS)
else
NO_OF_GUNICORN_WORKERS := 5
endif

.PHONY: help clean install test build image publish
.DEFAULT_GOAL = help

#help: List available tasks on this project
help:
	@grep -E '^#[a-zA-Z\.\-]+:.*$$' $(MAKEFILE_LIST) | tr -d '#' | awk 'BEGIN {FS = ": "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

#version: Show current version of appstore
version:
	echo ${VERSION}

#clean: Remove old build artifacts and installed packages
clean:
	${MANAGE} flush
	${PYTHON} -m pip uninstall -y -r requirements.txt

#install: Install application along with required development packages
install: install.artillery
	${PYTHON} -m pip install --upgrade pip
	${PYTHON} -m pip install -r requirements.txt

#test: Run all tests
test:
	$(foreach brand,$(BRANDS),SECRET_KEY=${SECRET_KEY} DEV_PHASE=stub DJANGO_SETTINGS_MODULE=appstore.settings.$(brand)_settings ${MANAGE} test $(APP_LIST);)

#install.artillery: Install required packages for artillery testing
install.artillery:
	cd artillery-tests
	npm install

#test.artillery: Run artillery testing
test.artillery:
ifndef ARTILLERY_ENV
	$(error ARTILLERY_ENVIRONMENT not set (smoke|load))
endif
ifndef ARTILLERY_TARGET
	$(error ARTILLERY_TARGET not set (should point to the base URL of appstore, e.g. "http://localhost:8000"))
endif
	export TEST_USERS_PATH=artillery-tests/payloads/${ARTILLERY_ENV} && ${MANAGE} shell < bin/createtestusers.py
	cd artillery-tests; \
	ls -1 tests | xargs -L1 -I%TEST_NAME% npx artillery run tests/%TEST_NAME% --quiet --environment ${ARTILLERY_ENV} --target ${ARTILLERY_TARGET}
	

#start: Run the gunicorn server
start:
	if [ -z ${SETTINGS_MODULE} ]; then make help && echo "\n\nPlease set the DJANGO_SETTINGS_MODULE environment variable\n\n"; exit 1; fi
	${MANAGE} makemigrations
	${MANAGE} migrate
	${MANAGE} addingwhitelistedsocialapp
	${MANAGE} shell < bin/superuser.py
	${MANAGE} shell < bin/authorizeuser.py
	if [ "${CREATE_TEST_USERS}" = "true" ]; then ${MANAGE} shell < bin/createtestusers.py; fi
	${MANAGE} collectstatic --clear --no-input
	${MANAGE} spectacular --file ./appstore/schema.yml
	# bash /usr/src/inst-mgmt/bin/populate_env.sh /usr/src/inst-mgmt/appstore/static/frontend/env.json
	gunicorn --bind 0.0.0.0:8000 --log-level=debug --pythonpath=./appstore appstore.wsgi:application --workers=${NO_OF_GUNICORN_WORKERS}

#build: Build the Docker image
build:
	docker build --no-cache --pull -t ${DOCKER_IMAGE} -f Dockerfile .
	docker tag ${DOCKER_IMAGE} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}
	docker tag ${DOCKER_IMAGE} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}-${COMMIT_HASH}

#build.test: Test the Docker image (requires docker compose)
build.test:
	docker-compose -f docker-compose.test.yml up --build --exit-code-from appstore

build.postgresql:
	docker-compose -f docker-compose-postgresql.yaml up --build

#publish.image: Push the Docker image
publish: build
	docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}
	docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}-${COMMIT_HASH}
