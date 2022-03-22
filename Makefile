PYTHON          := /usr/bin/env python3
VERSION_FILE    := ./appstore/appstore/_version.py
VERSION         := $(shell grep __version__ ${VERSION_FILE} | cut -d " " -f 3 ${VERSION_FILE} | tr -d '"')
COMMIT_HASH     := $(shell git rev-parse --short HEAD)
SHELL           := /bin/bash

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

DOCKER_OWNER    := helxplatform

DOCKER_APP      := appstore
DOCKER_TAG      := ${VERSION}
DOCKER_IMAGE    := ${DOCKER_OWNER}/${DOCKER_APP}:$(DOCKER_TAG)
SECRET_KEY      := $(shell openssl rand -base64 12)
APP_LIST        ?= api appstore core frontend middleware product
BRANDS          := braini cat heal restartr scidas eduhelx argus
MANAGE	        := ${PYTHON} appstore/manage.py

ifdef GUNICORN_WORKERS
NO_OF_GUNICORN_WORKERS := $(GUNICORN_WORKERS)
else
NO_OF_GUNICORN_WORKERS := 5
endif

# Use only when working locally
ENV_FILE := $(PWD)/.env
ifdef SET_BUILD_ENV_FROM_FILE
ENVS_FROM_FILE := ${SET_BUILD_ENV_FROM_FILE}
else
ENVS_FROM_FILE := true
endif

ifdef DEBUG
DEBUG := ${DEBUG}
else
DEBUG := false
endif

ifdef LOG_LEVEL
LOG_LEVEL = ${LOG_LEVEL}
else
LOG_LEVEL := "info"
endif

ifeq "${DEBUG}" "true"
LOG_LEVEL := "debug"
endif

ifeq "${ENVS_FROM_FILE}" "true"
include $(ENV_FILE)
export
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
install:
	${PYTHON} -m pip install --upgrade pip
	${PYTHON} -m pip install -r requirements.txt

#test: Run all tests
test:
	$(foreach brand,$(BRANDS),SECRET_KEY=${SECRET_KEY} DEV_PHASE=stub DJANGO_SETTINGS_MODULE=appstore.settings.$(brand)_settings ${MANAGE} test $(APP_LIST);)

#start: Run the gunicorn server
start:	build.postgresql.local
	if [ -z ${DJANGO_SETTINGS_MODULE} ]; then make help && echo "\n\nPlease set the DJANGO_SETTINGS_MODULE environment variable\n\n"; exit 1; fi
	${MANAGE} makemigrations
	${MANAGE} migrate
	${MANAGE} addingwhitelistedsocialapp
	${MANAGE} shell < bin/superuser.py
	${MANAGE} shell < bin/authorizeuser.py
	if [ "${CREATE_TEST_USERS}" = "true" ]; then ${MANAGE} shell < bin/createtestusers.py; fi
	${MANAGE} collectstatic --clear --no-input
	${MANAGE} spectacular --file ./appstore/schema.yml
	if [[ "${DEV_PHASE}" != "local" ]]; then bash bin/populate_env.sh ./appstore/static/frontend/env.json; fi
	gunicorn --bind 0.0.0.0:8000 --log-level=${LOG_LEVEL} --pythonpath=./appstore appstore.wsgi:application --workers=${NO_OF_GUNICORN_WORKERS}

#build: Build the Docker image
build:
	docker build --no-cache --pull -t ${DOCKER_IMAGE} -f Dockerfile .
	docker tag ${DOCKER_IMAGE} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}
	docker tag ${DOCKER_IMAGE} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}-${COMMIT_HASH}

#build.test: Test the Docker image (requires docker compose)
build.test:
	docker-compose -f docker-compose.test.yml up --build --exit-code-from appstore

build.postgresql.local:
	if [[ "${POSTGRES_ENABLED}" = "true" && "${DEV_PHASE}" = "local" ]]; then docker-compose -f ./docker-compose-postgresql.yaml up -d --build; fi

#publish.image: Push the Docker image
publish: build
	docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}
	docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}-${COMMIT_HASH}
