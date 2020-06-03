"""
OAuth backend that authenticates user created using info returned from oauth service, docs at:
    https://github.com/heliumdatacommons/auth_microservice/wiki/API-and-Use
"""

import requests

from rest_framework import status

from django.contrib.auth.models import User
from django.conf import settings


class OAuth:
    def authenticate(self, request, username=None, access_token=None, first_name=None,
                     last_name=None, email=''):

        if not access_token or not username:
            return None

        url = '{}validate_token'.format(settings.OAUTH_SERVICE_SERVER_URL)
        auth_header_str = 'Basic {}'.format(settings.OAUTH_APP_KEY)
        response = requests.get(url, headers={'Authorization': auth_header_str},
                                params={'provider': 'auth0',
                                        'access_token': access_token})

        if response.status_code != status.HTTP_200_OK:
            return None

        # set email field to username if not returned from auth service
        if not email:
            email = username

        try:
            user = User.objects.get(username=username)
            # update user email field if needed
            if user.email != email:
                user.email = email
                user.save()

        except User.DoesNotExist:
            # create a linked user account
            user = User.objects.create_user(
                username, email,
                first_name=first_name,
                last_name=last_name,
                password=None,
            )

            user.is_staff = False
            user.is_active = True
            user.save()

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
