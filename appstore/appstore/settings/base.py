"""
General django settings for appstore project.

For product specific settings see <product>_settings.py
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

APPSTORE_NESTED_SETTINGS_DIR = Path(__file__).parent.resolve(strict=True)
APPSTORE_CONFIG_DIR = APPSTORE_NESTED_SETTINGS_DIR.parent
DJANGO_PROJECT_ROOT_DIR = APPSTORE_CONFIG_DIR.parent
LOG_DIR = DJANGO_PROJECT_ROOT_DIR.parent / "log"

# localhost/0.0.0.0 required when DEBUG is false
ALLOWED_HOSTS = [
    "*",
    "127.0.0.1",
    "0.0.0.0",
]

# Generic Django settings https://docs.djangoproject.com/en/3.2/ref/settings/
ADMIN_URL = "/admin"
APPEND_SLASH = True
LANGUAGE_CODE = "en-us"
SITE_ID = 4
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["SECRET_KEY"]
# SECURITY WARNING: don't run with debug turned on in production!
# Empty quotes equates to false in kubernetes env.
DEBUG_STRING = os.environ.get("DEBUG", "")
if DEBUG_STRING.lower() == "false":
    DEBUG_STRING = ""
DEBUG = bool(DEBUG_STRING)
# stub, local, dev, val, prod.
DEV_PHASE = os.environ.get("DEV_PHASE", "local")
TYCHO_MODE = os.environ.get("TYCHO_MODE", "null" if DEV_PHASE == "stub" else "live")

# Variables used for an external Tycho app registry.
# ToDo: Consider setting the default value of TYCHO_APP_REGISTRY_REPO to 
# "https://github.com/helxplatform/helx-apps/raw" and remove any other similar
# variable.  Maybe don't set and raise a fatal error if not set (still remove
# other similar variables).
EXTERNAL_TYCHO_APP_REGISTRY_ENABLED = os.environ.get("EXTERNAL_TYCHO_APP_REGISTRY_ENABLED", "false").lower()
EXTERNAL_TYCHO_APP_REGISTRY_REPO = os.environ.get("EXTERNAL_TYCHO_APP_REGISTRY_REPO", "")
# Make sure TYCHO_APP_REGISTRY_REPO ends with "/" or suffix is removed by urljoin.
if EXTERNAL_TYCHO_APP_REGISTRY_REPO != "":
    EXTERNAL_TYCHO_APP_REGISTRY_REPO += "/" if not EXTERNAL_TYCHO_APP_REGISTRY_REPO.endswith("/") else ""
EXTERNAL_TYCHO_APP_REGISTRY_BRANCH = os.environ.get("EXTERNAL_TYCHO_APP_REGISTRY_BRANCH", "master")
EXTERNAL_TYCHO_APP_REGISTRY_APP_SPECS_DIR = os.environ.get("EXTERNAL_TYCHO_APP_REGISTRY_APP_SPECS_DIR", "app-specs")
DOCKSTORE_APP_SPECS_DIR_URL = os.environ.get("DOCKSTORE_APP_SPECS_DIR_URL")

# DJANGO and SAML login toggle flags, lower cased for ease of comparison
ALLOW_DJANGO_LOGIN = os.environ.get(
    "ALLOW_DJANGO_LOGIN",
    "True" if DEV_PHASE == "local" or DEV_PHASE == "stub" else "False",
).lower()
ALLOW_SAML_LOGIN = os.environ.get("ALLOW_SAML_LOGIN", "False").lower()
IMAGE_DOWNLOAD_URL = os.environ.get(
    "IMAGE_DOWNLOAD_URL", "https://braini-metalnx.renci.org/metalnx"
)

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "corsheaders",
    "crispy_forms",
    "rest_framework",
    "drf_spectacular",
]

LOCAL_APPS = [
    "api",
    "core",
    "appstore",
    "frontend",
    "middleware",
    "product",
]

OAUTH_PROVIDERS = os.environ.get("OAUTH_PROVIDERS", "").split(",")
for PROVIDER in OAUTH_PROVIDERS:
    if PROVIDER != '':
        THIRD_PARTY_APPS.append(f"allauth.socialaccount.providers.{PROVIDER}")

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

WSGI_APPLICATION = "appstore.wsgi.application"
ROOT_URLCONF = "appstore.urls"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.auth.middleware.RemoteUserMiddleware",
    "middleware.filter_whitelist_middleware.AllowWhiteListedUserOnly",
    "middleware.session_idle_timeout.SessionIdleTimeout",
]

SESSION_IDLE_TIMEOUT = int(os.environ.get("DJANGO_SESSION_IDLE_TIMEOUT", 300))
EXPORTABLE_ENV = os.environ.get("EXPORTABLE_ENV",None)
if EXPORTABLE_ENV != None: EXPORTABLE_ENV = EXPORTABLE_ENV.split(':')
else: EXPORTABLE_ENV = []

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.RemoteUserBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

ACCOUNT_ADAPTER = "appstore.adapter.LoginRedirectAdapter"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = os.environ.get("ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http")
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 3
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 86400  # 1 day in seconds
ACCOUNT_LOGOUT_REDIRECT_URL = "/helx"
LOGIN_REDIRECT_URL = "/helx/workspaces/login/success"
LOGIN_URL = "/accounts/login"
LOGIN_WHITELIST_URL = "/login_whitelist/"
OIDC_SESSION_MANAGEMENT_ENABLE = True
SAML_URL = "/accounts/saml"
SAML_ACS_URL = "/saml2_auth/acs/"
SOCIALACCOUNT_QUERY_EMAIL = ACCOUNT_EMAIL_REQUIRED
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "offline"}}
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            str(DJANGO_PROJECT_ROOT_DIR / "templates"),
        ],
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                # TODO remove when django local app "core" is deprecated and
                # removed. Expose settings in context or other drf endpoints
                # and set context data in views.py for the template/view being
                # rendered.
                "appstore.context_processors.global_settings",
            ],
        },
    },
]
CRISPY_TEMPLATE_PACK = "bootstrap4"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_DEFAULTS = {
    "TITLE": "HeLx Platform Appstore API Definition",
    "DESCRIPTION": "https://github.com/helxplatform/appstore",
    "VERSION": "0.0.0",
}

DB_DIR = Path(os.environ.get("OAUTH_DB_DIR", DJANGO_PROJECT_ROOT_DIR))
DB_FILE = Path(os.environ.get("OAUTH_DB_FILE", "DATABASE.sqlite3"))

# Default DEV_PHASE is always local, which enables sqlite3.
POSTGRES_ENABLED = os.environ.get("POSTGRES_ENABLED", "true")
if POSTGRES_ENABLED == "true":
    DATABASES = {
        "default": {
            "ENGINE": f"django.db.backends.{os.environ.get('PG_DB_ENGINE', 'postgresql')}",
            "NAME": os.environ.get("PG_DB_DATABASE", "postgres"),
            "USER": os.environ.get("PG_DB_USERNAME", "postgres"),
            "PASSWORD": os.environ.get("PG_DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("PG_DB_HOST", "0.0.0.0"),
            "PORT": os.environ.get("PG_DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DB_DIR / DB_FILE,
        }
    }

STATIC_URL = "/static/"
STATIC_ROOT = DJANGO_PROJECT_ROOT_DIR / "static"
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = "587"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "appstore@renci.org")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
RECIPIENT_EMAILS = os.environ.get("RECIPIENT_EMAILS", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.environ.get("APPSTORE_DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
DEFAULT_SUPPORT_EMAIL = os.environ.get(
    "APPSTORE_DEFAULT_SUPPORT_EMAIL", EMAIL_HOST_USER
)

# Logging
MIN_LOG_LEVEL = "INFO"
LOG_LEVEL = "DEBUG" if DEBUG else os.environ.get("LOG_LEVEL", MIN_LOG_LEVEL)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,  # keep Django's default loggers
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
        "verbose2": {
            "format": "[%(asctime)s %(levelname)s %(filename)s->%(funcName)s():%(lineno)s]: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[%(asctime)s] %(levelname)s %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
        "timestampthread": {
            "format": "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s] [%(name)-25.25s  ]  %(message)s",
        },
    },
    "handlers": {
        "syslog": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "system_warnings.log",
            "formatter": "timestampthread",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
        },
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose2",
        },
        "djangoLog": {
            "level": LOG_LEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django_debug.log",
            "formatter": "timestampthread",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
        },
        "app_store_log": {
            "level": LOG_LEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "app_store.log",
            "formatter": "timestampthread",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "propagate": False,
            "level": LOG_LEVEL
        },
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.template": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "admin": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
        },
        "tycho.client": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
        },
        "tycho.kube": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
        },
    },
}

# All debug settings
if DEBUG and DEV_PHASE in ("local", "stub", "dev"):
    INSTALLED_APPS += [
        "debug_toolbar",
    ]

    INTERNAL_IPS = [
        "127.0.0.1",
    ]

    CORS_ALLOWED_ORIGINS = [
        "https://localhost:3000",
        "https://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # We don't want to create security vulnerabilities through CORS policy. Only allow on dev deployments where the UI may be running on another origin.
    CORS_ALLOW_CREDENTIALS = True

    CSRF_TRUSTED_ORIGINS = [
        "localhost",
        "127.0.0.1",
    ]

    DEBUG_MIDDLEWARE = [
        "corsheaders.middleware.CorsMiddleware",
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]

    # Add debug middleware early on so it doesn't conflict or process through
    # middleware that would disrupt in the process
    MIDDLEWARE[1:1] = DEBUG_MIDDLEWARE

SAML2_AUTH = {
    # Optional settings below
    "DEFAULT_NEXT_URL": "/helx/workspaces/login/success",  # Custom target redirect URL after the user get logged in. Default to /admin if not set. This setting will be overwritten if you have parameter ?next= specificed in the login URL.
    "CREATE_USER": "TRUE",  # Create a new Django user when a new user logs in. Defaults to True.
    "NEW_USER_PROFILE": {
        "USER_GROUPS": [],  # The default group name when a new user logs in
        "ACTIVE_STATUS": True,  # The default active status for new users
        "STAFF_STATUS": True,  # The staff status for new users
        "SUPERUSER_STATUS": False,  # The superuser status for new users
    },
    "ATTRIBUTES_MAP": {  # Change Email/UserName/FirstName/LastName to corresponding SAML2 userprofile attributes.
        "email": "mail",
        "username": "uid",
        "first_name": "givenName",
        "last_name": "sn",
    },
    "ASSERTION_URL": os.environ.get("SAML2_AUTH_ASSERTION_URL"),
    "ENTITY_ID": os.environ.get(
        "SAML2_AUTH_ENTITY_ID"
    ),  # Populates the Issuer element in authn request
}

# Metadata is required, either remote url or local file path, check the environment
# determine the type based on the form of the value.  Default to UNC if there's nothing

metadata_source = os.environ.get("SAML_METADATA_SOURCE")
if metadata_source != None and type(metadata_source) is str and len(metadata_source) != 0: 
    metadata_source_components = metadata_source.split(':')
    if len(metadata_source_components) > 1:
        metadata_source_scheme = metadata_source_components[0]
        if metadata_source_scheme == "http" or metadata_source_scheme == "https":
           SAML2_AUTH["METADATA_AUTO_CONF_URL"] = metadata_source
        else: SAML2_AUTH["METADATA_LOCAL_FILE_PATH"] = metadata_source
    else: SAML2_AUTH["METADATA_LOCAL_FILE_PATH"] = metadata_source
