from __future__ import annotations

import logging
import time
import os
import re
import uuid
from typing import Optional
from dataclasses import asdict

from django.conf import settings
from django.contrib.auth import logout


from rest_framework import status as drf_status, viewsets, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status

from allauth import socialaccount

from app import parse_compose
from kube import KubeClient, HelxAppManager, HelxInstManager, HelxUserManager, StatusQuery
from kube.models import HelxUserSpec
from kube import labels as kube_labels
from registry import get_registry
from core.models import IrodAuthorizedUser, UserIdentityToken

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

# TODO: Structured Logging
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy singletons: created on first request, not at import time.
# ---------------------------------------------------------------------------

_kube_client: KubeClient | None = None


def _get_kube() -> KubeClient:
    """Lazily initialise the Kubernetes client (only needed at runtime)."""
    global _kube_client
    if _kube_client is None:
        _kube_client = KubeClient()
    return _kube_client


def _get_helxapp_mgr() -> HelxAppManager:
    kc = _get_kube()
    return HelxAppManager(kc.custom, kc.namespace)


def _get_helxinst_mgr() -> HelxInstManager:
    kc = _get_kube()
    return HelxInstManager(kc.custom, kc.namespace)


def _get_helxuser_mgr() -> HelxUserManager:
    kc = _get_kube()
    return HelxUserManager(kc.custom, kc.namespace)


def _get_status_query() -> StatusQuery:
    kc = _get_kube()
    return StatusQuery(kc.apps, kc.namespace)


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


def extract_app_resources(app_id: str) -> tuple[Resources, Resources]:
    """Extract minimum (request) and maximum (limit) resources for an app.

    Uses app to parse the compose spec.  Prefers ``x-helx-resources``
    bounds when available; falls back to standard compose
    ``deploy.resources``.

    Returns (minimum_resources, maximum_resources).
    """
    app = get_registry().get_app(app_id)
    compose = get_registry().get_spec(app_id)
    compose_app = parse_compose(compose, ext=app.ext)

    svc = compose_app.get_service(app_id)
    if svc is None and compose_app.services:
        # Fall back to the first service if the primary name doesn't match
        svc = compose_app.services[0]

    if svc is None:
        return (
            Resources(0, 0, 0, 0),
            Resources(0, 0, 0, 0),
        )

    if svc.resource_bounds is not None:
        bounds = svc.resource_bounds
        minimum = Resources(
            cpus=to_cpus(bounds.cpu.min) if bounds.cpu and bounds.cpu.min else 0,
            gpus=int(bounds.gpu.min) if bounds.gpu and bounds.gpu.min else 0,
            memory=bounds.memory.min if bounds.memory and bounds.memory.min else 0,
            ephemeralStorage=bounds.ephemeral_storage.min if bounds.ephemeral_storage and bounds.ephemeral_storage.min else 0,
        )
        maximum = Resources(
            cpus=to_cpus(bounds.cpu.max) if bounds.cpu and bounds.cpu.max else 0,
            gpus=int(bounds.gpu.max) if bounds.gpu and bounds.gpu.max else 0,
            memory=bounds.memory.max if bounds.memory and bounds.memory.max else 0,
            ephemeralStorage=bounds.ephemeral_storage.max if bounds.ephemeral_storage and bounds.ephemeral_storage.max else 0,
        )
        if bounds.lock:
            maximum = minimum
        return minimum, maximum

    # Fall back to standard compose limits / requests
    minimum = Resources(
        cpus=to_cpus(svc.requests.cpu) if svc.requests.cpu else 0,
        gpus=int(svc.requests.gpu) if svc.requests.gpu else 0,
        memory=svc.requests.memory if svc.requests.memory else 0,
        ephemeralStorage=svc.requests.ephemeral_storage if svc.requests.ephemeral_storage else 0,
    )
    maximum = Resources(
        cpus=to_cpus(svc.limits.cpu) if svc.limits.cpu else 0,
        gpus=int(svc.limits.gpu) if svc.limits.gpu else 0,
        memory=svc.limits.memory if svc.limits.memory else 0,
        ephemeralStorage=svc.limits.ephemeral_storage if svc.limits.ephemeral_storage else 0,
    )
    return minimum, maximum

def validate_request_resources(request_cpu, request_gpu, request_memory, request_ephemeral, minimum_resources, maximum_resources, username=None, app_id=None):
    """
    Validate requested resources against minimum and maximum limits.

    Logs validation failures with user and app context for monitoring.
    """
    # Helper to log validation failures
    def log_validation_failure(resource_type, requested, limit, limit_type, reason):
        context = []
        if username:
            context.append(f"user={username}")
        if app_id:
            context.append(f"app_id={app_id}")
        context.append(f"resource={resource_type}")
        context.append(f"requested={requested}")
        context.append(f"{limit_type}={limit}")
        context.append(f"reason={reason}")

        logger.warning(f"Resource validation failed: {' '.join(context)}")

    if request_cpu is not None and request_cpu < float(minimum_resources.cpus):
        log_validation_failure("cpu", request_cpu, minimum_resources.cpus, "minimum", "below_minimum")
        return Response(
            f"Invalid resources requested. Cannot allocate more than {minimum_resources.cpus} cpus.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_cpu is not None and request_cpu > float(maximum_resources.cpus):
        log_validation_failure("cpu", request_cpu, maximum_resources.cpus, "maximum", "exceeds_maximum")
        return Response(
            f"Invalid resources requested. Cannot allocate more than {maximum_resources.cpus} cpus.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_gpu is not None and request_gpu < int(minimum_resources.gpus):
        log_validation_failure("gpu", request_gpu, minimum_resources.gpus, "minimum", "below_minimum")
        return Response(
            f"Invalid resources requested. Cannot allocate less than {minimum_resources.gpus} gpus.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_gpu is not None and request_gpu > int(maximum_resources.gpus):
        log_validation_failure("gpu", request_gpu, maximum_resources.gpus, "maximum", "exceeds_maximum")
        return Response(
            f"Invalid resources requested. Cannot allocate more than {maximum_resources.gpus} gpus.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_memory is not None and to_bytes(request_memory) < to_bytes(minimum_resources.memory):
        log_validation_failure("memory", request_memory, minimum_resources.memory, "minimum", "below_minimum")
        return Response(
            f"Invalid resources requested. Cannot allocate less than {minimum_resources.memory} memory.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_memory is not None and to_bytes(request_memory) > to_bytes(maximum_resources.memory):
        log_validation_failure("memory", request_memory, maximum_resources.memory, "maximum", "exceeds_maximum")
        return Response(
            f"Invalid resources requested. Cannot allocate more than {maximum_resources.memory} memory.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_ephemeral is not None and to_bytes(request_ephemeral) < to_bytes(minimum_resources.ephemeralStorage):
        log_validation_failure("ephemeral_storage", request_ephemeral, minimum_resources.ephemeralStorage, "minimum", "below_minimum")
        return Response(
            f"Invalid resources requested. Cannot allocate less than {minimum_resources.ephemeralStorage} ephemeral storage.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )

    if request_ephemeral is not None and to_bytes(request_ephemeral) > to_bytes(maximum_resources.ephemeralStorage):
        log_validation_failure("ephemeral_storage", request_ephemeral, maximum_resources.ephemeralStorage, "maximum", "exceeds_maximum")
        return Response(
            f"Invalid resources requested. Cannot allocate more than {maximum_resources.ephemeralStorage} ephemeral storage.",
            status=drf_status.HTTP_400_BAD_REQUEST
        )


def to_bytes(memory):
    """
    Convert memory string into bytes
    - b
    - k/kb, ki
    - m/mb, mi
    - g/gb, gi,
    - t/tb, ti
    
    Ex: to_bytes("1M") == 1000000
    """
    units = {
        "b": 1,

        "k": 1e3,
        "kb": 1e3,
        "ki": 2**10,

        "m": 1e+6,
        "mb": 1e+6,
        "mi": 2**20,

        "g": 1e+9,
        "gb": 1e+9,
        "gi": 2**30,

        "t": 1e12,
        "tb": 1e12,
        "ti": 2**40
    }
    
    if isinstance(memory, int) or isinstance(memory, float): return memory

    memory = memory.replace(" ", "")
    match = re.match(r"(.*)([A-Za-z]+)", memory)
    if match is None: return 0
    
    try:
        number = float(match.group(1))
    except ValueError:
        return 0
    unit = match.group(2).lower()
    conversion = units.get(unit, 0)

    return number * conversion


def to_cpus(cpu) -> float:
    """Convert Kubernetes CPU quantities to cores as a float."""
    if isinstance(cpu, (int, float)):
        return float(cpu)
    if cpu in (None, ""):
        return 0.0

    cpu = str(cpu).strip()
    match = re.fullmatch(r"([0-9]*\.?[0-9]+)([numkKMGTPE]?)", cpu)
    if match is None:
        return 0.0

    value = float(match.group(1))
    suffix = match.group(2)
    multipliers = {
        "": 1.0,
        "n": 1e-9,
        "u": 1e-6,
        "m": 1e-3,
        "k": 1e3,
        "K": 1e3,
        "M": 1e6,
        "G": 1e9,
        "T": 1e12,
        "P": 1e15,
        "E": 1e18,
    }
    return value * multipliers.get(suffix, 0.0)


class AppViewSet(viewsets.GenericViewSet):
    """
    ViewSet for listing and retrieving available applications.

    Uses AppRegistry (backed by app) instead of the legacy TychoContext.
    """

    lookup_field = "app_id"
    lookup_url_kwarg = "app_id"

    def get_serializer_class(self):
        if self.action == "list":
            return AppSerializer
        elif self.action == "retrieve":
            return AppDetailSerializer

    def _app_to_response(self, resolved_app, minimum, maximum):
        """Build an App response object from a ResolvedApp + resources."""
        return App(
            name=resolved_app.name,
            app_id=resolved_app.app_id,
            description=resolved_app.description,
            detail=resolved_app.details,
            docs=resolved_app.docs_url,
            spec=resolved_app.spec_path,
            count=resolved_app.count,
            minimum_resources=asdict(minimum),
            maximum_resources=asdict(maximum),
        )

    def list(self, request):
        """Provide all available apps."""
        apps = {}

        for resolved_app in get_registry().list_apps():
            try:
                minimum, maximum = extract_app_resources(resolved_app.app_id)
                app_obj = self._app_to_response(resolved_app, minimum, maximum)
                apps[resolved_app.app_id] = asdict(app_obj)
            except Exception as e:
                logger.error(f"Could not parse {resolved_app.app_id}...continuing. {e}")
                continue

        apps = {key: value for key, value in sorted(apps.items())}
        logger.debug(f"apps:\n${apps}")
        serializer = self.get_serializer(data=apps)
        serializer.is_valid()
        if serializer.errors:
            logger.error(
                f"Serialization errors detected:\n{serializer.errors}\nWill attempt "
                f"to provide data to user."
            )
        # TODO change this to serializer.data after discovery on nested object data
        return Response(apps)

    def retrieve(self, request, app_id: Optional[str] = None):
        """Provide app details."""
        resolved_app = get_registry().get_app(app_id)
        minimum, maximum = extract_app_resources(app_id)
        app_obj = self._app_to_response(resolved_app, minimum, maximum)
        logger.debug(f"app:\n${app_obj}")

        serializer = self.get_serializer(data=asdict(app_obj))
        serializer.is_valid()
        if serializer.errors:
            logger.error(
                f"Serialization errors detected:\n{serializer.errors}\nWill attempt "
                f"to provide data to user."
            )
        return Response(serializer.validated_data)


class InstanceViewSet(viewsets.GenericViewSet):
    """
    ViewSet for managing running application instances.

    Uses kube.StatusQuery, HelxAppManager, and HelxInstManager instead
    of the legacy TychoContext.
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

    def get_queryset(self):
        """Return InstanceStatus objects for the current user."""
        return _get_status_query().by_username(self.request.user.username.lower())

    def _extract_sid_from_helxinst(self, helxinst):
        spec = helxinst.get("spec", {}) or {}
        reference_id = spec.get("referenceID")
        if reference_id:
            return reference_id
        env = spec.get("environment", {}) or {}
        guid = env.get("GUID")
        if guid:
            return guid

        name = (helxinst.get("metadata", {}) or {}).get("name", "")
        if "-" in name:
            return name.split("-", 1)[1]
        return None

    def _get_helxinst_record(self, sid, username):
        """Find the HelxInst CR backing an AppStore instance ID."""
        username = username.lower()
        for item in _get_helxinst_mgr().list():
            metadata = item.get("metadata", {}) or {}
            spec = item.get("spec", {}) or {}
            env = spec.get("environment", {}) or {}
            status = item.get("status", {}) or {}
            if (spec.get("userName") or "").lower() != username:
                continue
            if (
                spec.get("referenceID") == sid
                or env.get("GUID") == sid
                or metadata.get("name", "").endswith(f"-{sid}")
                or status.get("uuid") == sid
            ):
                return item
        return None

    def _normalize_status_instance_id(self, ist, username):
        """Prefer the AppStore GUID over any controller-derived UUID."""
        helxinst = self._get_helxinst_record(ist.instance_id, username)
        if helxinst is None and ist.controller_id:
            helxinst = self._get_helxinst_record(ist.controller_id, username)
        if helxinst is None:
            return ist

        sid = self._extract_sid_from_helxinst(helxinst)
        if sid:
            ist.instance_id = sid
        return ist

    def _get_instance_status(self, sid, username):
        """Resolve an AppStore sid to the matching deployment status."""
        active = self.get_queryset()
        for ist in active:
            ist = self._normalize_status_instance_id(ist, username)
            if ist.instance_id == sid or (ist.controller_id and ist.controller_id == sid):
                return ist

        helxinst = self._get_helxinst_record(sid, username)
        if helxinst is None:
            return None

        controller_uuid = (helxinst.get("status") or {}).get("uuid")
        if not controller_uuid:
            return None

        statuses = _get_status_query().by_controller_id(controller_uuid)
        for ist in statuses:
            if (ist.username or "").lower() == username.lower():
                # Keep the outward-facing AppStore sid stable for callers.
                ist.instance_id = sid
                return ist
        return None

    def _instance_from_status(self, ist, username, host):
        """Convert an InstanceStatus to the API Instance model."""
        app_name = ist.app_name or ""
        try:
            resolved = get_registry().get_app(app_name)
            name = resolved.name
            docs = resolved.docs_url
        except KeyError:
            name = app_name
            docs = ""

        # Aggregate resource usage across containers
        total_cpu = 0.0
        total_gpu = 0
        total_memory = 0.0
        total_ephemeral = ""
        for _cname, res in ist.resource_usage.items():
            total_cpu += to_cpus(res.get("cpu", 0))
            gpu_val = res.get("nvidia.com/gpu", 0)
            total_gpu += int(gpu_val) if gpu_val else 0
            total_memory += to_bytes(res.get("memory", "0"))
            if res.get("ephemeral-storage"):
                total_ephemeral = res["ephemeral-storage"]

        return Instance(
            name=name,
            docs=docs,
            aid=app_name,
            sid=ist.instance_id,
            fqsid=ist.name,
            workspace_name=ist.workspace_name,
            creation_time=ist.creation_time or "",
            cpus=total_cpu,
            gpus=total_gpu,
            memory=total_memory,
            ephemeralStorage=total_ephemeral,
            host=host,
            username=username,
            is_ready=ist.is_ready,
        )

    def get_instance(self, sid, username, host):
        ist = self._get_instance_status(sid, username)
        if ist is None:
            return None
        return self._instance_from_status(ist, username, host)

    def list(self, request):
        """Provide all active instances."""
        active = self.get_queryset()
        username = request.user.get_username().lower()
        host = get_host(request)
        instances = []

        if not host.lower() == "ambassador":
            for ist in active:
                ist = self._normalize_status_instance_id(ist, username)
                app_name = ist.app_name or ""
                logger.debug(f"\nActive instance type:\n{app_name}\n")

                try:
                    get_registry().get_app(app_name)
                except KeyError:
                    continue

                inst = self._instance_from_status(ist, username, host)
                instances.append(inst)
        else:
            logger.error(f"\nAmbassador seen as host:\n{host}\n")

        serializer = self.get_serializer(instances, many=True)
        return Response(serializer.data)

    def create(self, request):
        """Launch an instance of an app via the helxapp-controller."""
        username = request.user.get_username()

        serializer = self.get_serializer(data=request.data)
        logger.debug("checking if request is valid")
        serializer.is_valid(raise_exception=True)
        logger.debug("creating resource_request")
        resource_request = serializer.create(serializer.validated_data)
        logger.debug(f"resource_request: {resource_request}")
        irods_enabled = os.environ.get("IROD_HOST", '').strip()

        if irods_enabled != '':
            nfs_id = get_nfs_uid(username)
            os.environ["NFSRODS_UID"] = str(nfs_id)

        # Create identity token
        try:
            identity_token = UserIdentityToken.objects.create(user=request.user)
            logger.debug(f"Created identity token for user {username}")
        except Exception as e:
            logger.error(f"Failed to create identity token for user {username}: {type(e).__name__}: {str(e)}")
            return Response(
                {"message": "Failed to create authentication token"},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        app_id = serializer.data["app_id"]

        # Validate resources against bounds
        minimum_resources, maximum_resources = extract_app_resources(app_id)

        request_cpu = float(resource_request.cpus)
        request_gpu = int(resource_request.gpus)
        request_memory = to_bytes(resource_request.memory)
        request_ephemeral = to_bytes(resource_request.ephemeralStorage)

        validation_response = validate_request_resources(
            request_cpu, request_gpu, request_memory, request_ephemeral,
            minimum_resources, maximum_resources,
            username=username, app_id=app_id
        )
        if validation_response is not None:
            return validation_response

        # Build CRD specs
        host = get_host(request)
        instance_id = uuid.uuid4().hex[:32]
        k8s_user = username.lower()
        inst_name = f"{app_id}-{instance_id}"

        helxapp_spec = get_registry().build_helxapp(app_id)

        # Per-instance environment variables.  The controller merges these
        # with HelxApp-level env (instance values take precedence).
        # Each instance needs a unique base path so app routing lines up with
        # the launched service URL and per-instance proxying.
        proxy_path = f"/private/{app_id}/{k8s_user}/{instance_id}"
        inst_env = {
            "NB_PREFIX": proxy_path,
            "FB_BASEURL": proxy_path,
            "REFERENCE_ID": instance_id,
            "GUID": instance_id,
            "USER_NAME": k8s_user,
            "USER": k8s_user,
            "ACCESS_TOKEN": str(identity_token.token),
            "HOST": host,
        }

        helxinst_spec = get_registry().build_helxinst(
            app_id,
            k8s_user,
            reference_id=instance_id,
            resource_request={
                "cpu": str(resource_request.cpus),
                "memory": resource_request.memory,
                "gpu": str(resource_request.gpus),
                "ephemeral_storage": resource_request.ephemeralStorage or None,
            },
            environment=inst_env,
        )

        # Submit to Kubernetes
        try:
            stdnfs_pvc = os.environ.get("STDNFS_PVC", "stdnfs")
            parent_dir = os.environ.get("PARENT_DIR", "home")
            home_path = f"/{parent_dir}/{k8s_user}"
            user_spec = HelxUserSpec(
                environment={
                    "HOME": home_path,
                },
                volumes={
                    "home": f"{stdnfs_pvc}:{home_path}#{k8s_user}",
                },
            )
            user_labels = None
            if os.environ.get("LDAP_URI"):
                user_labels = {kube_labels.IDENTITY_SOURCE: "ldap"}
            _get_helxuser_mgr().ensure(k8s_user, user_spec, labels=user_labels)
            _get_helxapp_mgr().ensure(app_id, helxapp_spec)
            _get_helxapp_mgr().wait_for_reconcile(app_id)
            _get_helxinst_mgr().create(inst_name, helxinst_spec)
        except Exception as e:
            logger.error(f"Failed to create CRDs for {app_id}, user {username}: {type(e).__name__}: {e}")
            try:
                identity_token.delete()
            except Exception:
                pass
            return Response(
                {"message": "failed to submit app start."},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Update identity token with consumer ID
        try:
            identity_token.consumer_id = identity_token.compute_app_consumer_id(instance_id)
            identity_token.save()
            logger.debug(f"Updated identity token with consumer_id {identity_token.consumer_id} for user {username}")
        except Exception as e:
            logger.error(
                f"Failed to save identity token for user {username}, app {app_id}, "
                f"instance {instance_id}: {type(e).__name__}: {str(e)}"
            )
            try:
                _get_helxinst_mgr().delete(inst_name)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup instance after token save failure: {str(cleanup_error)}")
            return Response(
                {"message": "Failed to save authentication token"},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        resolved_app = get_registry().get_app(app_id)
        s = InstanceSpec(
            username=k8s_user,
            app_id=app_id,
            name=resolved_app.name,
            host=host,
            resources=resource_request.resources,
            ip=None,
            port=0,
            svc_id=inst_name,
            sys_id=instance_id,
        )

        serializer = InstanceSpecSerializer(data=asdict(s))
        try:
            serializer.is_valid(raise_exception=True)
            logger.info(f"Launched app {app_id}-{instance_id} for user {username}")
            return Response(serializer.validated_data)
        except serializers.ValidationError as e:
            logger.error(f"Failed to launch app {app_id} for user {username}; exception: {str(e)}")
            try:
                _get_helxinst_mgr().delete(inst_name)
            except Exception:
                pass
            try:
                identity_token.delete()
                logger.debug(f"Deleted identity token for failed instance launch: user={username}, app={app_id}")
            except Exception as token_error:
                logger.error(
                    f"Failed to delete identity token after instance validation failure: "
                    f"user={username}, app={app_id}, error={str(token_error)}"
                )
            return Response(
                serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST
            )

    def retrieve(self, request, sid=None):
        """Provide active instance details."""
        username = request.user.get_username().lower()
        host = get_host(request)

        if sid is not None:
            instance = self.get_instance(sid, username, host)
            if instance is not None:
                serializer = self.get_serializer(instance)
                return Response(serializer.data)

        logger.error(f"\n{sid} not found\n")
        return Response(status=drf_status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def is_ready(self, request, sid=None):
        username = request.user.get_username().lower()
        host = get_host(request)

        if sid is not None:
            instance = self.get_instance(sid, username, host)
            if instance is not None:
                return Response({'is_ready': instance.is_ready})
            # Deployment may not exist yet — controller hasn't reconciled.
            # Return not-ready rather than 404 so the UI keeps polling.
            logger.debug(f"Instance {sid} not found yet, returning is_ready=false")
            return Response({'is_ready': False})

        return Response(status=drf_status.HTTP_404_NOT_FOUND)

    def destroy(self, request, sid=None):
        """Delete an instance via the helxapp-controller."""
        serializer = self.get_serializer(data={"sid": sid})
        serializer.is_valid(raise_exception=True)
        instance_id = serializer.validated_data["sid"]

        helxinst = self._get_helxinst_record(instance_id, request.user.username)
        if helxinst is None:
            return Response(status=drf_status.HTTP_404_NOT_FOUND)

        spec = helxinst.get("spec", {}) or {}
        owner = (spec.get("userName") or "").lower()
        if owner != request.user.username.lower():
            logger.warning(f"User {request.user.username} attempted to terminate app id {sid} owned by user {owner}")
            return Response(status=drf_status.HTTP_403_FORBIDDEN)

        inst_name = (helxinst.get("metadata", {}) or {}).get("name")
        if not inst_name:
            return Response(status=drf_status.HTTP_404_NOT_FOUND)

        logger.info(f"Terminating app id {sid} for user {request.user.username}")
        _get_helxinst_mgr().delete(inst_name)

        # Clean up identity tokens
        try:
            consumer_id = UserIdentityToken.compute_app_consumer_id(instance_id)
            tokens = UserIdentityToken.objects.filter(user=request.user, consumer_id=consumer_id)
            token_count = tokens.count()
            tokens.delete()
            logger.info(f"Deleted {token_count} identity token(s) for terminated instance: user={request.user.username}, sid={sid}")
        except Exception as token_error:
            logger.error(
                f"Failed to delete identity tokens for terminated instance: "
                f"user={request.user.username}, sid={sid}, error={type(token_error).__name__}: {str(token_error)}"
            )
        time.sleep(2)
        return Response({"status": "success"})

    def partial_update(self, request, sid=None):
        """Update resources on a running instance."""
        serializer = InstanceModifySerializer(data=request.data)
        serializer.is_valid()

        data = serializer.validated_data
        username = request.user.get_username()
        host = get_host(request)
        instance = self.get_instance(sid, username, host)

        if instance is None:
            return Response(status=drf_status.HTTP_404_NOT_FOUND)

        app_id = instance.aid
        minimum_resources, maximum_resources = extract_app_resources(app_id)

        request_cpu = float(data["cpu"]) if "cpu" in data else None
        request_gpu = float(data["gpu"]) if "gpu" in data else None
        request_memory = to_bytes(data["memory"]) if "memory" in data else None
        request_ephemeral = None

        validation_response = validate_request_resources(
            request_cpu, request_gpu, request_memory, request_ephemeral,
            minimum_resources, maximum_resources,
            username=username, app_id=app_id
        )
        if validation_response is not None:
            return validation_response

        # Build updated HelxInstSpec and patch the CRD
        resource_dict = {}
        if "cpu" in data:
            resource_dict["cpu"] = str(data["cpu"])
        if "memory" in data:
            resource_dict["memory"] = data["memory"]
        if "gpu" in data:
            resource_dict["gpu"] = str(data["gpu"])

        helxinst_spec = get_registry().build_helxinst(
            app_id,
            username.lower(),
            resource_request=resource_dict if resource_dict else None,
        )

        helxinst = self._get_helxinst_record(sid, username)
        if helxinst is None:
            return Response(status=drf_status.HTTP_404_NOT_FOUND)

        inst_name = (helxinst.get("metadata", {}) or {}).get("name")
        if not inst_name:
            return Response(status=drf_status.HTTP_404_NOT_FOUND)
        try:
            _get_helxinst_mgr().update(inst_name, helxinst_spec)
        except Exception as e:
            logger.error(f"Failed to update instance {inst_name}: {e}")
            return Response(
                {"message": "Failed to update instance."},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.debug(f"Updated instance {inst_name}")
        return Response({"status": "success"})


class UsersViewSet(viewsets.GenericViewSet):
    """
    UsersViewSet - ViewSet for managing user information.

    This ViewSet provides endpoints to retrieve details of the currently logged-in user 
    and to handle user logout.

    Endpoints:
    - List User Details:
        - URL: /users/
        - HTTP Method: GET
        - Method: list
        - Description: Provides details of the currently logged-in user, including their 
                       username and access token. This endpoint is designed to support 
                       scenarios where a reverse proxy (like nginx) performs authentication 
                       before proxying a request.

    - Logout:
        - URL: /users/logout/
        - HTTP Method: POST
        - Method: logout
        - Description: Logs out the current user and returns a success message.

    Note:
    - The ViewSet uses a private method '_get_access_token' to retrieve the user's 
      access token from the session.
    - 'EmptySerializer' is used for the 'logout' action, likely to simply validate the 
      request without any specific data.
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
            # This is not necessarily an error, since authorization (access token)
            # may or may not be used, i.e., with authentication via sessionid.
            logger.debug(f"Authorization not set for {request.user.username}")
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
        username = request.user.username if request.user.is_authenticated else "anonymous"
        logger.info(f"User {username} logged out via API")
        logout(request)
        data = {"success": "Successfully logged out"}
        return Response(data=data, status=status.HTTP_200_OK)


class LoginProviderViewSet(viewsets.GenericViewSet):
    """
    LoginProviderViewSet - ViewSet for retrieving login provider information.

    This ViewSet provides information about the available social login providers 
    from `allauth`, Django's default login, and any product-specific providers like SSO. 
    It's designed to list out these available authentication providers and their 
    respective login URLs.

    Attributes:
    - permission_classes: Allow any user (authenticated or not) to access this endpoint.
    - serializer_class: Uses `LoginProviderSerializer` to serialize the data.

    Methods:
    - get_queryset: Returns the global `settings` object.
    - _get_social_providers: A private method to retrieve social login providers 
                             from `allauth`.
    - _get_django_provider: A private method to check if Django's default login 
                            is enabled and to get its login URL.
    - _get_product_providers: A private method to check for any product-specific 
                              SSO providers and retrieve their details.
    - _get_login_providers: An aggregation method that combines the results 
                            from the above three methods to get a comprehensive 
                            list of login providers.
    - list: The main endpoint which uses `_get_login_providers` to fetch all 
            available login providers and returns them after serialization.

    Endpoints:
    - List Login Providers:
        - URL: /providers/
        - HTTP Method: GET
        - Method: list
        - Description: Lists all available authentication/login providers 
                       and their respective login URLs.
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
            adapter = socialaccount.adapter.get_adapter(request)
            providers = adapter.list_providers(request)
            for provider in providers:
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

        if settings.ALLOW_SAML_LOGIN == "true":
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
    AppContextViewSet - ViewSet for retrieving brand/product configuration information.

    This ViewSet provides information about the brand or product's configuration settings.
    It fetches the settings from the global `settings` object and serializes them using 
    the `AppContextSerializer`.

    Attributes:
    - permission_classes: Allow any user (authenticated or not) to access this endpoint.
    - serializer_class: Uses `AppContextSerializer` to serialize the data.

    Methods:
    - get_queryset: Returns the global `settings` object.
    - list: Fetches specific configuration settings from the `settings` object, 
            combines them with specific environment variables from `EXPORTABLE_ENV`, 
            and returns the aggregated data.

    Endpoints:
    - List Brand/Product Configuration:
        - URL: /context/
        - HTTP Method: GET
        - Method: list
        - Description: Lists specific configuration settings related to the brand or product 
                       and certain environment variables specified in `EXPORTABLE_ENV`.
    """

    permission_classes = [AllowAny]
    serializer_class = AppContextSerializer

    def get_queryset(self):
        return settings

    def list(self, request):
        settings = self.get_queryset()
        data = asdict(settings.PRODUCT_SETTINGS)
        data['dockstore_app_specs_dir_url'] = settings.DOCKSTORE_APP_SPECS_DIR_URL

        data['env'] = {}
        for k,v in sorted(os.environ.items()): 
            if k in settings.EXPORTABLE_ENV: data['env'][k] = v
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)
