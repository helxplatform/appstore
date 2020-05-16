FROM python:3.7

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
ENV DJANGO_SECRET_KEY djangosecretkey

RUN adduser --disabled-login --home $HOME --shell /bin/bash --uid $UID $USER && \
   chown -R $UID:$UID $HOME
#Switch the working directory.
WORKDIR $APP_HOME

#Install pycopg2 for postgresql.
RUN pip install psycopg2~=2.6
RUN apt-get update 
RUN apt-get install -y postgresql-client


# Install Virtual Environment
RUN pip install --upgrade pip
COPY . .
#RUN git clone --branch metadata https://github.com/helxplatform/tycho.git

RUN set -x && \
# Upgrade Pip and install app dependencies
	pip install --upgrade pip && \
	pip install -r tycho/requirements.txt && \
	pip install -r ./requirements.txt && \
# why is this not in requirements.txt?
	pip install psycopg2~=2.6 netifaces

EXPOSE 8000

#CMD [ "gunicorn", "--bind", ":8000", "--timeout=5000", \
#	"--log-level", "debug", \
#	"--env", "DJANGO_SETTINGS_MODULE=CS_AppsStore.settings.braini_settings", \
#	"CS_AppsStore.wsgi:application" ]

CMD ["python manage.py runserver --settings=CS_AppsStore.settings.${DJANGO_SETTINGS}_settings 0.0.0.0:8000 "]
