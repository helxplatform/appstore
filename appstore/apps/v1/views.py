import logging
from dataclasses import asdict
import time

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from rest_framework import status as drf_status, viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tycho.context import ContextFactory, Principal

from .models import Service, ServiceSpec, App, ResourceRequest
from .serializers import ServiceSerializer, AppDetailSerializer, AppSerializer, ResourceSerializer, ServiceSpecSerializer, ServiceIdentifierSerializer

# TODO: Structured Logging
logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
tycho = ContextFactory.get(
    context_type=settings.TYCHO_MODE,
    product=settings.APPLICATION_BRAND)


def get_host(request):
    if "HTTP_HOST" in request.META:
        host = request.META["HTTP_HOST"]
    else:
        host = "127.0.0.1"
    return host


def parse_spec_resources(app_id, spec):
    """
    Parse spec dictionary based on docker-compose definition files managed by tycho.

    https://github.com/compose-spec/compose-spec/blob/master/deploy.md#memory
    https://github.com/compose-spec/compose-spec/blob/master/deploy.md#cpus
    """
    services = spec['services']
    app_scope = services[app_id]
    resource_scope = app_scope['deploy']['resources']
    limits = resource_scope['limits']
    reservations = resource_scope['reservations']
    return limits, reservations


def search_for_gpu_reservation(reservations):
    """
    GPU info will be nested under devices. Because there could be multiple devices we
    need to find the GPU device from the list, if it exists.

    Currently exits on the first GPU spec, and assumes the spec is defining a generic
    GPU and count. This is not a requirement of docker-compose spec, see capabilities
    https://github.com/compose-spec/compose-spec/blob/master/deploy.md#capabilities
    for more details.
    """
    for d in reservations.get('devices', {}).items():
        if d.get('capabilities') == 'gpu':
            # Returning 0 for now if a device id is specified, gpu spec needs to be
            # further defined for app-prototypes and tycho.
            # https://github.com/compose-spec/compose-spec/blob/master/deploy.md
            # #device_ids
            return d.get('count', 0)
    # TODO what is the behavior the frontend should exhibit if a spec doesn't define
    # a GPU reservation? Do we want to pass 0, or `null`? What's the impact for the
    # user flow?
    # We may not find a GPU in the spec, in fact right now no specs have a GPU, but
    # we are providing minimum reservations to the front end from the spec.
    return 0


# TODO fetch by user instead of iterating all?
# sanitize input to avoid injection.
def get_social_tokens(username):
    social_token_model_objects = ContentType.objects.get(
        model="socialtoken").model_class().objects.all()
    access_token = None
    refresh_token = None
    for obj in social_token_model_objects:
        if obj.account.user.username == username:
            access_token = obj.token
            refresh_token = obj.token_secret if obj.token_secret else None
            break
        else:
            continue
    # with DRF and the user interaction in social auth we need username to be a string
    # when it is passed to `tycho.start` otherwise it will be a `User` object and there
    # will be a serialization failure from this line of code:
    # tycho.context.TychoContext.start
    #    principal_params = {"username": principal.username, "access_token":
    #    principal.access_token, "refresh_token": principal.refresh_token}
    #    principal_params_json = json.dumps(principal_params, indent=4)
    return str(username), access_token, refresh_token


class AppViewSet(viewsets.GenericViewSet):
    """
    Tycho App information.
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'app_id'
    lookup_url_kwarg = 'app_id'

    def get_queryset(self):
        return tycho.apps

    def get_serializer_class(self):
        if self.action == 'list':
            return AppSerializer
        elif self.action == 'retrieve':
            return AppDetailSerializer

    def list(self, request):
        """
        Provide all available apps.
        """
        apps = {}

        for app_id, app_data in self.get_queryset().items():
            spec = tycho.get_spec(app_id)
            logger.debug(f"\n\n Spec data for {app_id}\n{spec}\n\n")
            limits, reservations = parse_spec_resources(app_id, spec)

            # TODO GPUs can be defined differently in docker-compose than in the
            # submission from Tycho to k8s, how do we want to handle this?
            # https://github.com/compose-spec/compose-spec/blob/master/deploy.md
            # #capabilities
            # https://github.com/helxplatform/tycho/search?q=gpu
            gpu = search_for_gpu_reservation(reservations)

            spec = App(
                app_data['name'],
                app_id,
                app_data['description'],
                app_data['details'],
                app_data['docs'],
                app_data['spec'],
                reservations.get('cpu', 0),
                gpu,
                reservations.get('memory', 0)
            )

            apps[app_id] = asdict(spec)


        apps = {key: value for key, value in sorted(apps.items())}
        serializer = self.get_serializer(data=apps)
        serializer.is_valid()
        if serializer.errors:
            logger.error(f"Serialization errors detected:\n{serializer.errors}\nWill attempt to provide data to user.")
        # TODO change this to serializer.data after discovery on nested object data
        return Response(apps)

    def retrieve(self, request, app_id=None):
        """
        Provide app details.
        """
        app_data = self.get_queryset()[app_id]
        spec = tycho.get_spec(app_id)
        limits, reservations = parse_spec_resources(app_id, spec)

        gpu = search_for_gpu_reservation(reservations)

        app = App(
            app_data['name'],
            app_id,
            app_data['description'],
            app_data['details'],
            app_data['docs'],
            app_data['spec'],
            reservations.get('cpu', 0),
            gpu,
            reservations.get('memory', 0)
        )

        logger.debug(f"\n\n App Definition:\n{app}\n\n")
        serializer = self.get_serializer(data=asdict(app))
        serializer.is_valid()
        if serializer.errors:
            logger.error(f"Serialization errors detected:\n{serializer.errors}\nWill attempt to provide data to user.")
        return Response(serializer.validated_data)


class ServiceViewSet(viewsets.GenericViewSet):
    """
    Active user services.
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'sid'
    lookup_url_kwarg = 'sid'

    def get_serializer_class(self):
        if self.action == 'create':
            return ResourceSerializer
        elif self.action == 'destroy':
            return ServiceIdentifierSerializer
        else:
            return ServiceSerializer

    def get_queryset(self):
        status = tycho.status({
            'username': self.request.user.username
        })
        return status.services

    def list(self, request):
        """
        Provide all active services.
        """
        active_services = self.get_queryset()

        services = []
        for service in active_services:
            logger.debug(f"\nService:\n{service}\n\n")
            # Note that total_util is formatted differently than service['util']
            # TODO confirm which to use going forward and format based on standard.
            logger.debug(f"\nTotal Utilization:\n{service.total_util}\n\n")
            # TODO could probably pull this list and search it locally instead of a
            # call per loop.
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

        serializer = self.get_serializer(data=services, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

    def create(self, request):
        """
        Given an app id and resources pass the information to Tycho to start a service
        instance of an app.
        """

        serializer = self.get_serializer(data=request.data)
        logger.debug(serializer)
        serializer.is_valid(raise_exception=True)
        resource_request = serializer.create(serializer.validated_data)

        # TODO update social query to fetch user.
        tokens = get_social_tokens(request.user)
        logger.debug("Tokens fetched for user.")
        principal = Principal(*tokens)
        logger.debug("Principal built.")

        app_id = serializer.data['app_id']
        system = tycho.start(principal, app_id, resource_request.resources)
        logger.debug(f"Spec submitted to Tycho. \n\n {system}\n\n")

        s = ServiceSpec(principal.username,
                        app_id,
                        tycho.apps[app_id]['name'],
                        get_host(request),
                        resource_request.resources,
                        system.services[0].ip_address,
                        system.services[0].port,
                        system.services[0].identifier,
                        system.identifier)

        logger.debug(f"Final service spec \n\n {s} \n\n")

        # TODO: better status capture from Tycho on submission
        if s:
            serializer = ServiceSpecSerializer(data=asdict(s))
            try:
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)
            except serializers.ValidationError:
                # Delete invalid service configuration that we won't be tracking
                # for the user.
                tycho.delete({"name": system.services[0].identifier})
                return Response(serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST)
        else:
            # Failed to construct a tracked service instance, attempt to remove
            # potentially created instance rather than leaving it hanging.
            tycho.delete({"name": system.services[0].identifier})
            return Response({"message": "failed to submit app start."},
                            status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, sid=None):
        """
        Provide active service details.
        """
        active_services = self.get_queryset()

        for service in active_services:
            if service.identifier == sid:
                app = tycho.apps.get(service.app_id.rpartition('-')[0], {})
                inst = Service(app.get('name'),
                               app.get('docs'),
                               service.identifier,
                               service.app_id,
                               service.creation_time,
                               service.total_util['cpu'],
                               service.total_util['gpu'],
                               service.total_util['memory'])

                logger.debug(f"\nInstance:\n{inst}\n\n")
                serializer = self.get_serializer(data=asdict(inst))
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)

        logger.debug(f"\n{sid} not found\n")
        return Response(status=drf_status.HTTP_404_NOT_FOUND)

    def destroy(self, request, sid=None):
        """
        Submit service id (sid) to tycho for removal.
        """

        serializer = self.get_serializer(data={'sid': sid})
        serializer.is_valid(raise_exception=True)
        logger.debug(f"\nDeleting: {sid}")
        response = tycho.delete({"name": serializer.validated_data['sid']})
        # TODO How can we avoid this sleep? Do we need an immediate response beyond
        # a successful submission? Can we do a follow up with Web Sockets or SSE
        # to the front end?
        time.sleep(2)
        logger.debug(f"\nDelete response: {response}")
        return Response(response)
