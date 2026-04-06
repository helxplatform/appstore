"""Convert resolved registry apps to HelxApp / HelxInst CRD specs."""

from __future__ import annotations

import os

from appspec import parse_compose, to_k8s_resources, bounds_to_resource_bounds
from kube.models import (
    AmbassadorSpec,
    AppServiceSpec,
    ContainerResources,
    HelxAppSpec,
    HelxInstSpec,
    PortSpec,
    ResourceSpec,
    SecurityContext,
)
from registry.models import ResolvedApp

# Standard ambassador prefix — routes /private/<app>/<user>/<uuid>/ to this
# service. Uses Go template expressions resolved by the controller at
# deployment time.
_AMBASSADOR_PREFIX = (
    "/private/{{ .system.AppClassName }}/{{ .system.UserName }}/{{ .system.UUID }}/"
)


def build_helxapp_spec(app: ResolvedApp, compose_spec: dict) -> HelxAppSpec:
    """Convert a resolved app + its docker-compose into a HelxAppSpec.

    Uses appspec.parse_compose() to extract services, ports, resources,
    bounds, and helx_vars from the compose spec.
    """
    compose_app = parse_compose(compose_spec, ext=app.ext)
    svc_specs: list[AppServiceSpec] = []
    ambassador_id = os.environ.get("AMBASSADOR_ID") or None
    ambassador_assigned = False

    for svc in compose_app.services:
        # Map ports: overlay the registry-level port as the service port
        ports: list[PortSpec] = []
        for cp in svc.ports:
            registry_port = app.services.get(svc.name)
            ports.append(PortSpec(
                container_port=cp,
                port=registry_port or 0,
            ))

        # If no ports from compose but registry declares this service
        if not ports and svc.name in app.services:
            rp = int(app.services[svc.name])
            ports.append(PortSpec(container_port=rp, port=rp))

        # Volumes: convert VolumeMount objects to DSL strings
        volumes: dict[str, str] = {}
        for v in svc.volumes:
            volumes[v.source] = v.to_dsl_string()

        # Resource bounds: prefer x-helx-resources; fall back to compose
        if svc.resource_bounds is not None:
            rb = bounds_to_resource_bounds(svc.resource_bounds)
        elif svc.limits.cpu or svc.requests.cpu:
            rb = {
                "limits": to_k8s_resources(svc.limits).to_dict(),
                "requests": to_k8s_resources(svc.requests).to_dict(),
            }
        else:
            rb = None

        # Ambassador: attach mapping to the first service that generates a
        # Kubernetes Service (non-zero port).  Subsequent services are
        # sidecars and do not need their own ambassador mapping.
        ambassador = None
        has_service_port = any(p.port for p in ports)
        if has_service_port and not ambassador_assigned:
            proxy_rewrite = None
            if app.proxy_rewrite_enabled:
                proxy_rewrite = app.proxy_rewrite_target or _AMBASSADOR_PREFIX
            ambassador = AmbassadorSpec(
                prefix=_AMBASSADOR_PREFIX,
                ambassador_id=ambassador_id,
                proxy_rewrite=proxy_rewrite,
            )
            ambassador_assigned = True

        svc_specs.append(AppServiceSpec(
            name=svc.name,
            image=svc.image,
            command=svc.command,
            environment=svc.environment,
            ports=ports,
            volumes=volumes,
            secrets_from=svc.secrets,
            security_context=app.security_context,
            resource_bounds=rb,
            ambassador=ambassador,
        ))

    return HelxAppSpec(
        app_class_name=app.app_id,
        services=svc_specs,
        helx_vars=compose_app.helx_vars or None,
    )


def build_helxinst_spec(
    app: ResolvedApp,
    username: str,
    resource_request: dict | None = None,
    security_context: SecurityContext | None = None,
    environment: dict[str, str] | None = None,
) -> HelxInstSpec:
    """Build a HelxInst spec for a user's launch request.

    :param app: The resolved app from the registry.
    :param username: The requesting user.
    :param resource_request: Resource dict, e.g.
        ``{"cpu": "2", "memory": "4Gi", "gpu": "1"}``.
    :param security_context: Instance-level override; falls back to
        app-level if not provided.
    :param environment: Per-instance environment variables (e.g.
        ``NB_PREFIX``, ``GUID``, ``ACCESS_TOKEN``).  Merged with
        app-level env at deploy time; instance values take precedence.
    """
    resources: dict[str, ContainerResources] = {}
    if resource_request:
        spec = ResourceSpec(
            cpu=resource_request.get("cpu"),
            memory=resource_request.get("memory"),
            gpu=resource_request.get("gpu"),
            ephemeral_storage=resource_request.get("ephemeral_storage"),
        )
        # Apply the same resource request to all services
        for svc_name in app.services:
            resources[svc_name] = ContainerResources(request=spec, limit=spec)

    sc = security_context or app.security_context

    return HelxInstSpec(
        app_name=app.app_id,
        user_name=username,
        resources=resources,
        security_context=sc,
        environment=environment,
    )
