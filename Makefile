PYTHON          := /usr/bin/env python3
VERSION_FILE    := ./appstore/appstore/_version.py
VERSION         := $(shell grep __version__ ${VERSION_FILE} | cut -d " " -f 3 ${VERSION_FILE} | tr -d '"')
DOCKER_REGISTRY := docker.io
DOCKER_OWNER    := helxplatform
DOCKER_APP	    := appstore
DOCKER_TAG      := ${VERSION}
DOCKER_IMAGE    := ${DOCKER_OWNER}/${DOCKER_APP}:$(DOCKER_TAG)
SECRET_KEY      := $(shell openssl rand -base64 12)
APP_LIST        ?= api appstore core frontend middleware product
BRANDS          := braini cat heal restartr scidas eduhelx
MANAGE	        := ${PYTHON} appstore/manage.py
SETTINGS_MODULE := ${DJANGO_SETTINGS_MODULE}

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
start:
	if [ -z ${SETTINGS_MODULE} ]; then make help && echo "\n\nPlease set the DJANGO_SETTINGS_MODULE environment variable\n\n"; exit 1; fi
	${MANAGE} makemigrations
	${MANAGE} migrate
	${MANAGE} addingwhitelistedsocialapp
	${MANAGE} shell < bin/superuser.py
	${MANAGE} shell < bin/authorizeuser.py
	${MANAGE} collectstatic --clear --no-input
	${MANAGE} spectacular --file ./appstore/schema.yml
	gunicorn --bind 0.0.0.0:8000 --log-level=debug --pythonpath=./appstore appstore.wsgi:application --workers=5

#build: Build the Docker image
build:
	docker build --no-cache --pull -t ${DOCKER_IMAGE} -f Dockerfile .

#build.test: Test the Docker image (requires docker compose)
build.test:
	docker-compose -f docker-compose.test.yml up --build --exit-code-from appstore

#publish.image: Push the Docker image
publish: build build.test
	docker tag ${DOCKER_IMAGE} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}
	docker push ${DOCKER_REGISTRY}/${DOCKER_IMAGE}