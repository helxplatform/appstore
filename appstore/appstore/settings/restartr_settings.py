from .base import *

APPLICATION_BRAND = "restartr"
APPLICATION_TITLE = "Restarting Research"
APPLICATION_LOGO = "/static/images/restartr/restartingresearch.png"
APPLICATION_COLOR = {
  "primary": "#ff6320",
  "secondary": "#ffd220"
}

SAML2_AUTH = {
    # Metadata is required, choose either remote url or local file path
    'METADATA_AUTO_CONF_URL': 'https://sso.unc.edu/metadata/unc',

    # Optional settings below
    'DEFAULT_NEXT_URL': '/apps/',  # Custom target redirect URL after the user get logged in. Default to /admin if not set. This setting will be overwritten if you have parameter ?next= specificed in the login URL.
    'CREATE_USER': 'TRUE', # Create a new Django user when a new user logs in. Defaults to True.
    'NEW_USER_PROFILE': {
        'USER_GROUPS': [],  # The default group name when a new user logs in
        'ACTIVE_STATUS': True,  # The default active status for new users
        'STAFF_STATUS': True,  # The staff status for new users
        'SUPERUSER_STATUS': False,  # The superuser status for new users
    },
    'ATTRIBUTES_MAP': {  # Change Email/UserName/FirstName/LastName to corresponding SAML2 userprofile attributes.
        'email': 'mail',
        'username': 'uid',
        'first_name': 'givenName',
        'last_name': 'sn',
    },
    'ASSERTION_URL': os.environ.get('SAML2_AUTH_ASSERTION_URL'),
    'ENTITY_ID': os.environ.get('SAML2_AUTH_ENTITY_ID'), # Populates the Issuer element in authn request
}
