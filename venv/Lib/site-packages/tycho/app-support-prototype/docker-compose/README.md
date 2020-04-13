# Docker Compose

## About

This example runs two docker containers to supply a Django-based web app.

```
$ docker ps
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS              PORTS                    NAMES
def85eff5f51        django_web          "python3 manage.py..."   10 minutes ago      Up 9 minutes        0.0.0.0:8000->8000/tcp   django_web_1
678ce61c79cc        postgres            "docker-entrypoint..."   20 minutes ago      Up 9 minutes        5432/tcp                 django_db_1
```

This can be an extremely simple app for us to practice with.

### Docker Compose File

The key is the Docker Compose file:

```
$ cat docker-compose.yml

version: '3'

services:
  db:
    image: postgres
  web:
    build: .
    command: python3 manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/code
    ports:
      - "8000:8000"
    depends_on:
      - db
```

**If we had the Docker Compose file and the Docker images available then we could launch this
app from Terra.**

The config also shows two important features:

* ports mapping
* volume mounting

These are two places where the Terra environment may want to provide a convention
for "app" authors.

### Conventions for "Apps"

How about the following?:

* always use "image" to specify and existing image on DockerHub or Quay
* the current working directory contains your docker compose file and is the location that should be mounted for persistent storage e.g. anything stored `.:/code` will be persisted
* ports, you specify those that are needed.  Port 80 is reserved but a port above 1024 is allowed.

## Dependencies

I just used the Docker you can install from https://docker.com.  It includes
Docker Compose.

## Creating

Follow the guide [here](https://docs.docker.com/compose/django/).

  sudo docker-compose run web django-admin.py startproject composeexample .

I already modified the database config.

## Launching

Launch with docker-compose command:

  docker-compose up

At this point, your Django app should be running at port 8000 on your Docker host.
On Docker for Mac and Docker for Windows, go to http://localhost:8000

Terminate with `ctrl+c` or

   docker-compose down

## See Also

See the following which were helpful in putting together this hello world:

* [Docker Compose and Django](https://docs.docker.com/compose/django/)
* [Hello world for Django](https://dfpp.readthedocs.io/en/latest/chapter_01.html)
* [A more detailed Django guide](https://docs.djangoproject.com/en/2.1/intro/tutorial01/)
