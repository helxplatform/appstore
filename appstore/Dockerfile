ARG BASE_CONTAINER=python:3.9.0-slim
FROM $BASE_CONTAINER

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Least privilege: Run as a non-root user.
ENV USER appstore
ENV APP_HOME /usr/src/inst-mgmt
ENV HOME /home/$USER
ENV UID 1000
ENV DJANGO_SETTINGS cat

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

RUN set -x && \
# Upgrade Pip and install app dependencies
	pip install --upgrade pip && \
	pip install -r ./requirements.txt

EXPOSE 8000

RUN chown -R 1000:0 /usr/src/inst-mgmt
RUN chmod -R g+w /usr/src/inst-mgmt

CMD ["/bin/bash","-c" ,"bin/appstore start ${DJANGO_SETTINGS}"]
