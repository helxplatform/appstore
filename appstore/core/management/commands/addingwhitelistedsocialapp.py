import os

from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if os.environ.get('OAUTH_PROVIDERS'):
            oauth_providers = os.environ['OAUTH_PROVIDERS'].split(',')
            for provider in oauth_providers:
                if not SocialApp.objects.filter(provider=provider.lower()):
                    social_app = SocialApp.objects.create(
                        name=os.environ[f'{provider.upper()}_NAME'],
                        client_id=os.environ[f'{provider.upper()}_CLIENT_ID'],
                        secret=os.environ.get(f'{provider.upper()}_SECRET'),
                        provider=provider,
                        key='',
                    )
                    social_app.sites.add(Site.objects.get(id=4))

                print(f"Added social applications {provider}.")

    if not Group.objects.filter(name='whitelisted'):
        Group.objects.create(name='whitelisted')
    print("Successfully added social applications GitHub and Google and whitelisted to the Group!")
