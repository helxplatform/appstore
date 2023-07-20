PYTHON           := /usr/bin/env python3
BRANCH_NAME	 	 := $(shell git branch --show-current | sed -r 's/[/]+/_/g')
override VERSION := ${BRANCH_NAME}-${VER}
COMMIT_HASH      := $(shell git rev-parse --short HEAD)
SHELL            := /bin/bash

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
BRANDS          := braini bdc heal restartr scidas eduhelx argus tracs eduhelx-sandbox eduhelx-dev
MANAGE	        := ${PYTHON} appstore/manage.py
SETTINGS_MODULE := ${DJANGO_SETTINGS_MODULE}

# smoke|test
ARTILLERY_ENV          := ${ARTILLERY_ENVIRONMENT}
# URL pointing to appstore base path, e.g. http://localhost:8000
ARTILLERY_TARGET       := ${ARTILLERY_TARGET}
# Duration in seconds that an Artillery load test lasts.
ARTILLERY_DURATION     := ${ARTILLERY_DURATION}
# Amount of users to instantiate per second during an Artillery load test.
ARTILLERY_ARRIVAL_RATE := ${ARTILLERY_ARRIVAL_RATE}

ifdef GUNICORN_WORKERS
NO_OF_GUNICORN_WORKERS := $(GUNICORN_WORKERS)
else
NO_OF_GUNICORN_WORKERS := 5
endif

# Use only when working locally
ENV_FILE := $(PWD)/.env
ifeq ("$(wildcard $(ENV_FILE))","")
_ := $(shell cp -v .env.default .env)
endif

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

ifndef LOG_LEVEL
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

init:
	git --version
	echo "Please make sure your git version is greater than 2.9.0. If it's not, this command will fail."
	git config --local core.hooksPath .githooks/

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
	cd artillery-tests; \
	npm install

#test.artillery: Run artillery testing
test.artillery:
ifndef ARTILLERY_ENV
	$(error ARTILLERY_ENVIRONMENT not set (smoke|load))
endif
ifndef ARTILLERY_TARGET
	$(error ARTILLERY_TARGET not set (should point to the base URL of appstore, e.g. "http://localhost:8000"))
endif
ifeq "${ARTILLERY_ENV}" "load"
ifndef ARTILLERY_DURATION
	$(error ARTILLERY_DURATION not set when ARTILLERY_ENVIRONMENT=load (seconds that a load test lasts))
endif
ifndef ARTILLERY_ARRIVAL_RATE
	$(error ARTILLERY_ARRIVAL_RATE not set when ARTILLERY_ENVIRONMENT=load (users instantiated per second))
endif
endif
	cd artillery-tests; \
	ls -1 tests | xargs -L1 -I%TEST_NAME% npx artillery run tests/%TEST_NAME% --environment ${ARTILLERY_ENV} --target ${ARTILLERY_TARGET}
	

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
	if [[ "${DEV_PHASE}" != "local" ]]; then ln -s /usr/src/inst-mgmt/appstore/static/favicon.ico /usr/src/inst-mgmt/appstore/static/images/favicon.ico; fi
	gunicorn --bind 0.0.0.0:8000 --log-level=${LOG_LEVEL} --pythonpath=./appstore appstore.wsgi:application --workers=${NO_OF_GUNICORN_WORKERS}

#build: Build the Docker image
build:
	if [ -z "$(VER)" ]; then echo "Please provide a value for the VER variable like this:"; echo "make VER=4 build"; false; fi;
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
