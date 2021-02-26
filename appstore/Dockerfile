ARG BASE_CONTAINER=python:3.9.0-slim
FROM $BASE_CONTAINER

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Configurable via the docker build command line with -p
ARG TYCHO_BRANCH=develop
# Least privilege: Run as a non-root user.
ENV USER appstore
ENV APP_HOME /usr/src/inst-mgmt
#ENV PYTHONPATH $APP_HOME:$APP_HOME/tycho
ENV HOME /home/$USER
ENV UID 1000
ENV DJANGO_SETTINGS braini
#ENV TYCHO_URL http://docker.for.mac.localhost:5000

RUN adduser --disabled-login --home $HOME --shell /bin/bash --uid $UID $USER && \
   chown -R $UID:$UID $HOME
#Switch the working directory.
WORKDIR $APP_HOME

RUN set -x && apt-get update && \
	chown -R $UID:$UID $APP_HOME && \
	apt-get install -y postgresql-server-dev-all \
	postgresql-client git build-essential \
	xmlsec1


# Install Virtual Environment
RUN pip install --upgrade pip
COPY . .

#RUN if [ ! -d $APP_HOME/tycho ]; then git clone --branch $TYCHO_BRANCH  https://github.com/helxplatform/tycho.git ; fi

RUN set -x && \
# Upgrade Pip and install app dependencies
	pip install --upgrade pip && \
	pip install -r ./requirements.txt
        #pip install tycho-api==1.0.2
    # why is this not in requirements.txt?
	#pip install psycopg2~=2.6 netifaces

EXPOSE 8000

RUN pip install -i https://pypi.org/simple/ --extra-index-url https://pypi.org/simple tycho-api==1.0.4

#CMD [ "gunicorn", "--bind", ":8000", "--timeout=5000", \
#	"--log-level", "debug", \
#	"--env", "DJANGO_SETTINGS_MODULE=appstore.settings.braini_settings", \
#	"appstore.wsgi:application" ]
RUN chown -R 1000:0 /usr/src/inst-mgmt
RUN chmod -R g+w /usr/src/inst-mgmt

CMD ["/bin/bash","-c" ,"bin/appstore start ${DJANGO_SETTINGS}"]
