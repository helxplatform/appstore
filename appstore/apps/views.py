import logging
from dataclasses import asdict

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tycho.context import ContextFactory, Principal

from .models import Service, ServiceSpec, App

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


class AppView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Provide all apps that have a blueprint in Tycho.
        """
        apps = {}

        for app_id, app_data in tycho.apps.items():
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
                reservations.get('memory', 0),
                gpu
            )

            apps[app_id] = asdict(spec)

        apps = {key: value for key, value in sorted(apps.items())}
        return Response(apps)

    def post(self, request):
        """
        Given an app id and resources pass the information to Tycho to start a service
        instance of an app.
        """

        # TODO: Structured Logging
        if not all(
                x in request.data.keys() for x in ['app_id', 'cpu', 'gpu', 'memory']):
            logger.debug(f"\n\nMissing resource argument: \n"
                         f"APP ID: {request.data.get('app_id', None)}\n"
                         f"CPU: {request.data.get('cpu', None)}\n"
                         f"GPU: {request.data.get('gpu', None)}\n"
                         f"Memory: {request.data.get('memory', None)}\n\n")
            return Response({"message": "app_id, cpu, gpu and memory fields required"},
                            status=status.HTTP_400_BAD_REQUEST)

        app_id = str(request.data['app_id'])
        cpu = str(request.data['cpu'])
        gpu = str(request.data['gpu'])
        memory = str(request.data['memory'])
        user = request.user

        logger.debug(f"\n\nResource arguments: \n"
                     f"User: {user}\n"
                     f"APP ID: {app_id}\n"
                     f"CPU: {cpu}\n"
                     f"GPU: {gpu}\n"
                     f"Memory: {memory}\n\n")

        # TODO, will the front end pass the metric? Do we ass
        # TODO move this and the above validation to a validator?
        # tycho/client.py:20 - mem_converter
        valid_memory_unit = ('M', 'G', 'T', 'P', 'E')
        if not memory.endswith(valid_memory_unit):
            return Response({"message": f"Invalid memory unit {memory}.\n"
                                        f"Valid memory units: {valid_memory_unit}"},
                            status=status.HTTP_400_BAD_REQUEST)

        resource_request = {
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": cpu,
                        "memory": memory,
                        "gpus": gpu,
                    },
                    "reservations": {
                        "cpus": cpu,
                        "memory": memory,
                        "gpus": gpu,
                    }
                }
            }
        }
        logger.debug(f"Resources requested \n\n {resource_request} \n\n")

        # TODO update social query.
        tokens = get_social_tokens(user)
        logger.debug("Tokens fetched for user.")

        principal = Principal(*tokens)
        logger.debug("Principal built.")

        logger.debug(f"\n\nPrincipal: \n"
                     f"{principal.username}\n"
                     f"{principal.access_token}\n"
                     f"{principal.refresh_token}\n\n")

        system = tycho.start(principal, app_id, resource_request)
        logger.debug(f"Spec submitted to Tycho. \n\n {system}\n\n")

        s = ServiceSpec(user,
                        app_id,
                        tycho.apps[app_id]['name'],
                        get_host(request),
                        resource_request,
                        system.services[0].ip_address,
                        system.services[0].port,
                        system.services[0].identifier,
                        system.identifier)

        logger.debug(f"Final service spec \n\n {s} \n\n")

        # TODO: better status capture from Tycho on submission
        if s:
            return Response(asdict(s))
        else:
            return Response({"message": "failed to submit app start."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Provide a list of all active service instances for a user.
        """
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

        # TODO research DRF dataclass serializer
        return Response(services)
