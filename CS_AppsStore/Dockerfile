FROM python:3.7

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
#Switch the working directory.
WORKDIR /usr/src/inst-mgmt

#Install pycopg2 for postgresql.
RUN pip install psycopg2~=2.6
RUN apt-get update
RUN apt-get install -y postgresql-client

# Install Virtual Environment
RUN pip install --upgrade pip
RUN pip install virtualenv
COPY ./requirements.txt /usr/src/inst-mgmt/requirements.txt
RUN virtualenv /usr/src/inst-mgmt/python_allauth
RUN /bin/bash -c "source /usr/src/inst-mgmt/python_allauth/bin/activate"
RUN pip install -r /usr/src/inst-mgmt/requirements.txt
RUN pip install pyyaml
RUN pip install netifaces 
RUN pip install jinja2 
RUN pip install kubernetes
RUN pip install requests
#RUN git clone https://github.com/muralikarthikk/tycho.git --branch ambassador
COPY ./tycho_api-5.0.2-py3-none-any.whl /usr/src/inst-mgmt/tycho_api-5.0.2-py3-none-any.whl
RUN mkdir /usr/local/lib/python3.7/site-packages/django/contrib/admin/templates/accounts
COPY ./login.html /usr/local/lib/python3.7/site-packages/django/contrib/admin/templates/accounts/
RUN pip install /usr/src/inst-mgmt/tycho_api-5.0.2-py3-none-any.whl
EXPOSE 8000
EXPOSE 5432
COPY . /usr/src/inst-mgmt

#CMD ["gunicorn", "--bind", ":8000", "CS_AppsStore.wsgi:application"]
