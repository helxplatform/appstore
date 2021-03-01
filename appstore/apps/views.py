import logging
from dataclasses import dataclass, asdict

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from tycho.context import ContextFactory

logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
tycho = ContextFactory.get(
    context_type=settings.TYCHO_MODE,
    product=settings.APPLICATION_BRAND)


@dataclass
class Service:
    """Tycho service attributes."""
    name: str
    docs: str
    identifier: str
    fully_qualified_identifier: str
    creation_time: str
    cpu: int
    gpu: int
    memory: float


class AppView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        apps = {k: v for k, v in sorted(tycho.apps.items(),
                                        key=lambda v: v[1]['name'])}
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
