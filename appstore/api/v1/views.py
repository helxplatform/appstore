import functools
import logging
from dataclasses import asdict
import time
import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required

from rest_framework import status as drf_status, viewsets, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status

from allauth import socialaccount

from tycho.context import ContextFactory, Principal
from core.models import IrodAuthorizedUser
from .exceptions import AuthorizationTokenUnavailable
from .models import Instance, InstanceSpec, App, LoginProvider, Resources, User
from .serializers import (
    InstanceSerializer,
    AppDetailSerializer,
    AppSerializer,
    ResourceSerializer,
    InstanceSpecSerializer,
    InstanceIdentifierSerializer,
    UserSerializer,
    LoginProviderSerializer,
    AppContextSerializer,
    InstanceModifySerializer,
    EmptySerializer,
)

from urllib.parse import urljoin

# TODO: Structured Logging
logger = logging.getLogger(__name__)


"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
contextFactory = ContextFactory()
if settings.EXTERNAL_TYCHO_APP_REGISTRY_ENABLED == "false":
    logger.debug (f"-- appstore.appstore.core.views.py: EXTERNAL_TYCHO_APP_REGISTRY_ENABLED is 'false', using Tycho built-in app registry file")
    tycho = contextFactory.get(
            context_type=settings.TYCHO_MODE, product=settings.APPLICATION_BRAND
    )
else:
    logger.debug (f"-- appstore.appstore.core.views.py: EXTERNAL_TYCHO_APP_REGISTRY_REPO is {settings.EXTERNAL_TYCHO_APP_REGISTRY_REPO}, EXTERNAL_TYCHO_APP_REGISTRY_BRANCH is {settings.EXTERNAL_TYCHO_APP_REGISTRY_BRANCH}, using external app registry file")
    # urljoin might not work as planned if the first part doesn't end with a slash.
    tycho_config_url = urljoin(settings.EXTERNAL_TYCHO_APP_REGISTRY_REPO, settings.EXTERNAL_TYCHO_APP_REGISTRY_BRANCH)
    logger.debug (f"tycho_config_url: {tycho_config_url}")
    tycho = contextFactory.get(
            context_type=settings.TYCHO_MODE, product=settings.APPLICATION_BRAND, tycho_config_url=tycho_config_url
    )


def get_nfs_uid(username):
    irod_auth_user = IrodAuthorizedUser.objects.get(user=username)
    if irod_auth_user is not None:
        return (irod_auth_user.uid)
    return (None)



def get_host(request):
    if "HTTP_HOST" in request.META:
        host = request.META["HTTP_HOST"]
    else:
        host = "127.0.0.1"
    return host


def parse_spec_resources(app_id, spec, app_data):
    """
    Parse spec dictionary based on docker-compose definition files managed by tycho.

    https://github.com/compose-spec/compose-spec/blob/master/deploy.md#memory
    https://github.com/compose-spec/compose-spec/blob/master/deploy.md#cpus
    """
    try:
        instances = spec["services"]
        app_scope = instances[app_id]
        resource_scope = app_scope["deploy"]["resources"]
        limits = resource_scope["limits"]
        reservations = resource_scope["reservations"]
        # If lock-resources is set to True, the reservations and limits should
        # be equal.
        lock_resources = app_data.get("lock-resources", False)
        if lock_resources:
            limits = reservations
        return limits, reservations
    except KeyError:
        logger.error(f"Could not parse {app_id}.\nInvalid spec {spec}")
        pass


def search_for_gpu_reservation(reservations):
    """
    GPU info will be nested under devices. Because there could be multiple devices we
    need to find the GPU device from the list, if it exists.

    Currently exits on the first GPU spec, and assumes the spec is defining a generic
    GPU and count. This is not a requirement of docker-compose spec, see capabilities
    https://github.com/compose-spec/compose-spec/blob/master/deploy.md#capabilities
    for more details.
    """
    for d in reservations.get("devices", {}).items():
        if d.get("capabilities") == "gpu":
            # Returning 0 for now if a device id is specified, gpu spec needs to be
            # further defined for app-prototypes and tycho.
            # https://github.com/compose-spec/compose-spec/blob/master/deploy.md
            # #device_ids
            return d.get("count", 0)
    # TODO what is the behavior the frontend should exhibit if a spec doesn't define
    # a GPU reservation? Do we want to pass 0, or `null`? What's the impact for the
    # user flow?
    # We may not find a GPU in the spec, in fact right now no specs have a GPU, but
    # we are providing minimum reservations to the front end from the spec.
    return 0


# TODO fetch by user instead of iterating all?
# sanitize input to avoid injection.
def get_social_tokens(username):
    social_token_model_objects = (
        ContentType.objects.get(model="socialtoken").model_class().objects.all()
    )
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

    lookup_field = "app_id"
    lookup_url_kwarg = "app_id"

    def get_queryset(self):
        return tycho.apps

    def get_serializer_class(self):
        if self.action == "list":
            return AppSerializer
        elif self.action == "retrieve":
            return AppDetailSerializer

    def list(self, request):
        """
        Provide all available apps.
        """
        apps = {}

        for app_id, app_data in self.get_queryset().items():
            try:
                spec = tycho.get_definition(app_id)
                limits, reservations = parse_spec_resources(app_id, spec, app_data)

                # TODO GPUs can be defined differently in docker-compose than in the
                # submission from Tycho to k8s, how do we want to handle this?
                # https://github.com/compose-spec/compose-spec/blob/master/deploy.md
                # #capabilities
                # https://github.com/helxplatform/tycho/search?q=gpu
                gpu = search_for_gpu_reservation(reservations)
                spec = App(
                    app_data["name"],
                    app_id,
                    app_data["description"],
                    app_data["details"],
                    app_data["docs"],
                    app_data["spec"],
                    app_data["count"],
                    asdict(
                        Resources(
                            reservations.get("cpus", 0),
                            gpu,
                            reservations.get("memory", 0),
                        )
                    ),
                    asdict(
                        Resources(limits.get("cpus", 0), gpu, limits.get("memory", 0))
                    ),
                )

                apps[app_id] = asdict(spec)
            except Exception as e:
                logger.error(f"Could not parse {app_id}...continuing. {e}")
                continue

        apps = {key: value for key, value in sorted(apps.items())}
        serializer = self.get_serializer(data=apps)
        serializer.is_valid()
        if serializer.errors:
            logger.error(
                f"Serialization errors detected:\n{serializer.errors}\nWill attempt "
                f"to provide data to user."
            )
        # TODO change this to serializer.data after discovery on nested object data
        return Response(apps)

    def retrieve(self, request, app_id=None):
        """
        Provide app details.
        """
        app_data = self.get_queryset()[app_id]
        spec = tycho.get_definition(app_id)
        limits, reservations = parse_spec_resources(app_id, spec, app_data)

        gpu = search_for_gpu_reservation(reservations)

        app = App(
            app_data["name"],
            app_id,
            app_data["description"],
            app_data["details"],
            app_data["docs"],
            app_data["spec"],
            app_data["count"],
            asdict(
                Resources(
                    reservations.get("cpus", 0), gpu, reservations.get("memory", 0)
                )
            ),
            asdict(Resources(limits.get("cpus", 0), gpu, limits.get("memory", 0))),
        )

        serializer = self.get_serializer(data=asdict(app))
        serializer.is_valid()
        if serializer.errors:
            logger.error(
                f"Serialization errors detected:\n{serializer.errors}\nWill attempt "
                f"to provide data to user."
            )
        return Response(serializer.validated_data)


class InstanceViewSet(viewsets.GenericViewSet):
    """
    Active user instances.
    """

    lookup_field = "sid"
    lookup_url_kwarg = "sid"

    def get_serializer_class(self):
        if self.action == "create":
            return ResourceSerializer
        elif self.action == "destroy":
            return InstanceIdentifierSerializer
        elif self.action == "partial_update":
            return InstanceModifySerializer
        else:
            return InstanceSerializer

    @functools.lru_cache(maxsize=16, typed=False)
    def get_principal(self, user):
        """
        Retrieve principal information from Tycho based on the request
        user.
        """
        tokens = get_social_tokens(user)
        principal = Principal(*tokens)
        return principal

    def get_queryset(self):
        status = tycho.status({"username": self.request.user.username})
        return status.services

    def list(self, request):
        """
        Provide all active instances.
        """

        active = self.get_queryset()
        principal = self.get_principal(request.user)
        username = principal.username
        host = get_host(request)
        instances = []

        # host should be in the form of the deployment domain, if ambassador is
        # marked as host then app url construction will be invalid.
        if not host.lower() == "ambassador":
            for instance in active:
                app_name = instance.app_id.replace(f"-{instance.identifier}", "")
                logger.debug(f"\nActive instance type:\n{app_name}\n")

                app = tycho.apps.get(app_name)
                if app:

                    inst = Instance(
                        app.get("name"),
                        app.get("docs"),
                        app_name,
                        instance.identifier,
                        instance.app_id,
                        instance.workspace_name,
                        instance.creation_time,
                        instance.total_util["cpu"],
                        instance.total_util["gpu"],
                        instance.total_util["memory"],
                        host,
                        username,
                    )
                    instances.append(asdict(inst))
        else:
            logger.error(f"\nAmbassador seen as host:\n{host}\n")

        serializer = self.get_serializer(data=instances, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

    def create(self, request):
        """
        Given an app id and resources pass the information to Tycho to start
        a instance of an app.
        """

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource_request = serializer.create(serializer.validated_data)
        irods_enabled = os.environ.get("IROD_ZONE",'').strip()
        # TODO update social query to fetch user.
        tokens = get_social_tokens(request.user)
        #Need to set an environment variable for the IRODS UID
        if irods_enabled != '':
            nfs_id = get_nfs_uid(request.user)
            os.environ[str(request.user)+"_NFSRODS_UID"] = str(nfs_id)

        principal = Principal(*tokens)

        app_id = serializer.data["app_id"]
        host = get_host(request)
        system = tycho.start(principal, app_id, resource_request.resources, host)

        s = InstanceSpec(
            principal.username,
            app_id,
            tycho.apps[app_id]["name"],
            host,
            resource_request.resources,
            system.services[0].ip_address,
            system.services[0].port,
            system.services[0].identifier,
            system.identifier,
        )
        # TODO: better status capture from Tycho on submission
        if s:
            serializer = InstanceSpecSerializer(data=asdict(s))
            try:
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)
            except serializers.ValidationError:
                # Delete invalid instance configuration that we won't be tracking
                # for the user.
                tycho.delete({"name": system.services[0].identifier})
                return Response(
                    serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST
                )
        else:
            # Failed to construct a tracked instance, attempt to remove
            # potentially created instance rather than leaving it hanging.
            tycho.delete({"name": system.services[0].identifier})
            return Response(
                {"message": "failed to submit app start."},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, sid=None):
        """
        Provide active instance details.
        """
        active = self.get_queryset()
        principal = self.get_principal(request.user)
        username = principal.username
        host = get_host(request)

        for instance in active:
            if instance.identifier == sid:
                app = tycho.apps.get(instance.app_id.rpartition("-")[0], {})
                inst = Instance(
                    app.get("name"),
                    app.get("docs"),
                    instance.identifier,
                    instance.app_id,
                    instance.creation_time,
                    instance.total_util["cpu"],
                    instance.total_util["gpu"],
                    instance.total_util["memory"],
                    app.get("app_id"),
                    host,
                    username,
                )

                serializer = self.get_serializer(data=asdict(inst))
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)

        logger.error(f"\n{sid} not found\n")
        return Response(status=drf_status.HTTP_404_NOT_FOUND)

    def destroy(self, request, sid=None):
        """
        Submit instance id (sid) to tycho for removal.
        """
        serializer = self.get_serializer(data={"sid": sid})
        serializer.is_valid(raise_exception=True)
        logger.debug(f"\nDeleting: {sid}")
        status = tycho.status({"name": serializer.validated_data["sid"]})
        if status.services != None and len(status.services) == 1:
            logger.info("service username: " + str(status.services[0].username))
            logger.info("request username: " + str(request.user.username))
            if status.services[0].username == request.user.username:
                response = tycho.delete({"name": serializer.validated_data["sid"]})
                # TODO How can we avoid this sleep? Do we need an immediate response beyond
                # a successful submission? Can we do a follow up with Web Sockets or SSE
                # to the front end?
                time.sleep(2)
                return Response(response)
            else: return Response(status=drf_status.HTTP_403_FORBIDDEN)
        else: return Response(status=drf_status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, sid=None):
        """
        Pass labels, cpu and memory to tycho for patching a running deployment.
        """

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data.update({"tycho-guid": sid})
        response = tycho.update(data)

        logger.debug(f"Update Response: {response}")
        return Response(response)


class UsersViewSet(viewsets.GenericViewSet):
    """
    User information.
    """

    def get_serializer_class(self):
        if self.action == "list":
            return UserSerializer
        elif self.action == "logout":
            return EmptySerializer

    def _get_access_token(self, request):
        if request.session.get("Authorization", None):
            return request.session["Authorization"].split(" ")[1]
        else:
            logger.error(f"Authorization not set for {request.user.username}")
            return None

    def list(self, request):
        """
        Provide logged in user details.

        Supports the use case where a reverse proxy like nginx is being used to
        test authentication of a principal before proxying a request upstream.
        """
        user = User(request.user.username, self._get_access_token(request), settings.SESSION_IDLE_TIMEOUT)
        serializer = self.get_serializer(data=asdict(user))
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

    @action(methods=["POST"], detail=False)
    def logout(self, request):
        logout(request)
        data = {"success": "Successfully logged out"}
        return Response(data=data, status=status.HTTP_200_OK)


class LoginProviderViewSet(viewsets.GenericViewSet):
    """
    Login provider information.
    """

    permission_classes = [AllowAny]
    serializer_class = LoginProviderSerializer

    def get_queryset(self):
        return settings

    def _get_social_providers(self, request, settings):
        """
        Get social login providers from allauth.
        """

        provider_data = []

        if (
            "allauth.account.auth_backends.AuthenticationBackend"
            in settings.AUTHENTICATION_BACKENDS
        ):
            for provider in socialaccount.providers.registry.get_list():
                provider_data.append(
                    asdict(
                        LoginProvider(provider.name, provider.get_login_url(request))
                    )
                )

        return provider_data

    def _get_django_provider(self, settings):
        """
        Check for default settings logins.
        """

        if settings.ALLOW_DJANGO_LOGIN == "true":
            return asdict(LoginProvider("Django", settings.LOGIN_URL))

    def _get_product_providers(self, settings):
        """
        Check for SSO defined in appstore settings.
        """

        if settings.ALLOW_SAML_LOGIN:
            # TODO can we get the provider name from metadata so that if
            # we support something beyond UNC we dont need another func
            # or clause? What happens if we have multiple SAML SSO providers
            # today it's handled with SAML_URL and the saml2_auth package,
            # but appears to be setup for one provider at a time.
            return asdict(
                LoginProvider(
                    "UNC Chapel Hill Single Sign-On",
                    settings.SAML_URL,
                )
            )

    def _get_login_providers(self, request):
        """
        Aggregate defined login providers for appstore.
        """
        settings = self.get_queryset()
        provider_data = []

        provider_data.extend(self._get_social_providers(request, settings))

        django = self._get_django_provider(settings)
        if django:
            provider_data.append(django)

        product = self._get_product_providers(settings)
        if product:
            provider_data.append(product)

        return provider_data

    def list(self, request):
        providers = self._get_login_providers(request)
        serializer = self.get_serializer(data=providers, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class AppContextViewSet(viewsets.GenericViewSet):
    """
    Brand/Product configuration information.
    """

    permission_classes = [AllowAny]
    serializer_class = AppContextSerializer

    def get_queryset(self):
        return settings

    def list(self, request):
        settings = self.get_queryset()
        data = asdict(settings.PRODUCT_SETTINGS)
        data['env'] = {}
        for k,v in sorted(os.environ.items()): 
            if k in settings.EXPORTABLE_ENV: data['env'][k] = v
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)
