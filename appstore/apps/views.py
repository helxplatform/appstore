import logging
from dataclasses import asdict

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from tycho.context import ContextFactory

from .models import Service, App

logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
tycho = ContextFactory.get(
    context_type=settings.TYCHO_MODE,
    product=settings.APPLICATION_BRAND)


class AppView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        apps = {}

        print(tycho.apps)

        for app_id, app_data in tycho.apps.items():

            spec = App(
                app_data['name'],
                app_id,
                app_data['description'],
                app_data['details'],
                app_data['docs'],
                app_data['spec']
            )

            apps[app_id] = asdict(spec)

        apps = {key: value for key, value in sorted(apps.items())}
        return Response(apps)


class ServiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status = tycho.status({
            'username': self.request.user.username
        })

        services = []

        for service in status.services:
            app = tycho.apps.get(service.app_id.rpartition('-')[0], {})

            inst = Service(app.get('name'),
                           app.get('docs'),
                           service.identifier,
                           service.app_id,
                           service.creation_time,
                           service.total_util['cpu'],
                           service.total_util['gpu'],
                           service.total_util['memory'])

            services.append(asdict(inst))

        return Response(services)
