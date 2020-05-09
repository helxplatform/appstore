#
# Copyright (c) Renaissance Computing Institute.
# Distributed under the terms of the MIT License.
#
# Use a Docker-appropriate ubuntu Python. Alpine does not play well with Python.
#
ARG BASE_CONTAINER=python:3.7.6-slim
FROM $BASE_CONTAINER

# Configurable via the docker build command line with -p
ARG TYCHO_BRANCH=master

# Least privilege: Run as a non-root user.
ENV USER appstore
ENV HOME /home/$USER
ENV UID 1000
RUN adduser --disabled-login --home $HOME --shell /bin/bash --uid $UID $USER && \
   chown -R $UID:$UID $HOME

# Configure the container environment
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV USE_WHITELIST_FILTER True
ENV APP_HOME /usr/src/inst-mgmt
ENV PYTHONPATH $APP_HOME:$APP_HOME/tycho
ENV DEBUG_LEVEL WARN
ENV VIRTUAL_ENV $APP_HOME/venv
ENV PATH "$VIRTUAL_ENV/bin:$PATH"
ENV DJANGO_SETTINGS braini

# Install runtime dependencies. Copy app code. Set ownership to non-root user.
USER root
WORKDIR $APP_HOME
COPY . .
RUN set -x && apt-get update && \
	chown -R $UID:$UID $APP_HOME && \
	apt-get install -y postgresql-server-dev-all \
	postgresql-client git build-essential

USER $USER
WORKDIR $APP_HOME
#git clone --single-branch \
#	--branch $TYCHO_BRANCH https://github.com/helxplatform/tycho.git && \
RUN set -x && \
# Virtual environment
	python -m venv venv && \
	. venv/bin/activate && \
# Upgrade Pip and install app dependencies
	pip install --upgrade pip && \
	pip install -r tycho/requirements.txt && \
	pip install -r ./requirements.txt && \	
# why is this not in requirements.txt?
	pip install psycopg2~=2.6 netifaces

# Run as a non-root user: least privilege.
USER $USER
# Expose the app's web endpoint.
EXPOSE 8000

#CMD [ "gunicorn", "--bind", ":8000", "--timeout=5000", \
#	"--log-level", "$DEBUG_LEVEL", \
#	"--env", "DJANGO_SETTINGS_MODULE=CS_AppsStore.settings.${DJANGO_SETTINGS}_settings", \
#	"CS_AppsStore.wsgi:application" ]
CMD [ "/bin/bash", "-c", "gunicorn --bind:8000 --timeout=5000 --log-level $DEBUG_LEVEL --env DJANGO_SETTINGS_MODULE=CS_AppsStore.settings.${DJANGO_SETTINGS}_settings CS_AppsStore.wsgi:application" ]

