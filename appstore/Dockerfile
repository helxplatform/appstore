ARG BASE_CONTAINER=python:3.7.6-slim
FROM $BASE_CONTAINER

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Configurable via the docker build command line with -p
ARG TYCHO_BRANCH=master
# Least privilege: Run as a non-root user.
ENV USER appstore
ENV APP_HOME /usr/src/inst-mgmt
ENV PYTHONPATH $APP_HOME:$APP_HOME/tycho
ENV HOME /home/$USER
ENV UID 1000
ENV DJANGO_SETTINGS braini
ENV TYCHO_URL http://docker.for.mac.localhost:5000
ENV SECRET_KEY C tr -dc "a-zA-Z0-9\!@#$%^&*()_+?><~\`;'" < /dev/urandom | fold -w ${1:-50} | head -n 1

RUN adduser --disabled-login --home $HOME --shell /bin/bash --uid $UID $USER && \
   chown -R $UID:$UID $HOME
#Switch the working directory.
WORKDIR $APP_HOME

RUN set -x && apt-get update && \
	chown -R $UID:$UID $APP_HOME && \
	apt-get install -y postgresql-server-dev-all \
	postgresql-client git build-essential


# Install Virtual Environment
RUN pip install --upgrade pip
COPY . .

RUN if [ ! -d $APP_HOME/tycho ]; then git clone --branch $TYCHO_BRANCH  https://github.com/helxplatform/tycho.git ; fi

RUN set -x && \
# Upgrade Pip and install app dependencies
	pip install --upgrade pip && \
	pip install -r tycho/requirements.txt && \
	pip install -r ./requirements.txt
    # why is this not in requirements.txt?
	#pip install psycopg2~=2.6 netifaces


EXPOSE 8000

#CMD [ "gunicorn", "--bind", ":8000", "--timeout=5000", \
#	"--log-level", "debug", \
#	"--env", "DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings", \
#	"appstore.wsgi:application" ]

CMD ["/bin/bash","-c" ,"bin/appstore start ${DJANGO_SETTINGS}"]
