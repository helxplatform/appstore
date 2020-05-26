# CommonsShare_AppStore

To run locally, follow the steps:

1) Clone the repository:

git clone https://github.com/heliumdatacommons/CommonsShare_AppStore.git

2) Navigate to the root directory:

```
CommonsShare_AppStore/              - root 
├── CS_AppsStore/                   - Project root
    ├── CS_AppsStore/               - Django root
    │   ├── ```__init__.py```
    │   ├── settings
    │   ├── urls.py
    │   └── wsgi.py
    └── manage.py
```

- Make sure you have virtualenv installed on your system and run the following command to create a virtual environment:

    ```virtualenv venv```

- Activate the virtual environment:

    ```source venv/bin/activate```

- Install the dependencies in the virtual environment:

    ```pip install -r requirements.txt```
    ```pip install tycho_api-5.0.2-py3-none-any.whl```

3) Navigate to the Django root, then cd into settings, and modify base.py:

Add the IP Address of the local machine to the list of ALLOWED_HOSTS if you are running the Django server on an AWS EC2 instance.

4) Navigate to the Project root and run the Django server:

```python manage.py runserver --settings=<settings_module>```
   - For braini, use ```--settings=CS_AppsStore.settings.braini_settings```
   - For scidas, use ```--settings=CS_AppsStore.settings.scidas_settings```
   - For catalyst, use ```--settings=CS_AppsStore.settings.cat_settings```

5) To install a new app, follow the steps below:

- Navigate to the Project root and run the following command:

    ```python manage.py startapp [app_name] --settings=<settings_module>```

- If your app should run for all brands, Update the CS_AppsStore/settings/base.py to add your app into INSTALLED_APPS list and add any other app specific settings as needed. Otherwise, update just the associated branded settings file. Refer to how existing apps such as tycho_nextflow or the phenotype app are set up.

- Add an app specific url pattern into CS_AppsStore/urls.py for better encapsulation. Follow the example done for PIVOT HAIL app as shown below:
    ```
    url('^tycho_nextflow/', include('tycho_nextflow.urls')),
    ```
- Create apps.py and ```__init__.py``` to have app-specific custom name, verbose_name, url and logo fields populated in AppConfig subclass. Refer to existing apps such as tycho_nextflow and phenotype apps to see how this is done. The custom verbose_name, url, and logo fields are used to dynamically populate the added apps to apps page for invocation of the app without need for specific coding.

6) Run the following commands to make sure database migration has taken place and all static files have been collectioned to the server:

```python manage.py migrate --settings=<settings_module>```

```python manage.py collectstatic --settings=<settings_module>```


7) Run Tycho locally:
   1) git clone https://github.com/helxplatform/tycho.git --branch amb-helx-v1.0
   2) python3 -m venv /venv/tycho
   3) . source /venv/tycho/bin/activate
   4) pip install -r /tycho/requirements.txt
   5) python /tycho/tycho/api.py -d



# Docker Development
## Dockerize Django, multiple Postgres databases, NginX, Gunicorn, virtualenv.
- The Django application is served by Gunicorn (WSGI application).
- We use NginX as reverse proxy and static files server. Static files persistently stored in volumes.
- Multiple Postgres databases can be used. Data are persistently stored in volumes.
- Python dependencies are managed through virtualenv.

## Requirements
- Install Docker and Docker-Compose

  [Docker CE for Ubuntu](https://docs.docker.com/install/linux/docker-ce/ubuntu/)
  
  ```sudo apt-get install docker-compose```
- Include the local_settings.py in the CS_AppStore directory.
- Include the pivot_hail.json in the pivot_hail/data/ directory.
- Modify the local_settings.py,


    ```DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'database1',
            'USER': 'postgres',
            'PASSWORD': '<password>',
            'HOST': 'database1',  # <-- IMPORTANT: same name as docker-compose service!
            'PORT': '5432',
        },
        'Backup': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'database2',
            'USER': 'postgres',
            'PASSWORD': '<password>',
            'HOST': 'database2',  # <-- IMPORTANT: same name as docker-compose service!
            'PORT': '5432',
        },
    }
    ```
    The passwords set here 
- Add the IP-Address to the list of Allowed Hosts.
    
## Build the image and run the containers
```sudo docker-compose up -d --build```

## To check the logs
```sudo docker-compose logs -f```

## To update the configuration for NginX and PostgreSql
The configuration files are available in config/ directory.

## Note
This Django project is not SSL-enabled.
