"""Convert resolved registry apps to HelxApp / HelxInst CRD specs."""

from __future__ import annotations

from kube.models import (
    AppServiceSpec,
    ContainerResources,
    HelxAppSpec,
    HelxInstSpec,
    PortSpec,
    ResourceSpec,
    SecurityContext,
)
from registry.models import ResolvedApp


def build_helxapp_spec(app: ResolvedApp, compose_spec: dict) -> HelxAppSpec:
    """Convert a resolved app + its docker-compose into a HelxAppSpec.

    Reads the docker-compose services to produce AppServiceSpec entries:
    - image, command, environment, ports from docker-compose
    - volumes from docker-compose
    - livenessProbe/readinessProbe from app.ext.kube
    - securityContext from app.security_context
    """
    compose_services = compose_spec.get("services", {})
    svc_specs: list[AppServiceSpec] = []

    for svc_name, svc_def in compose_services.items():
        image = svc_def.get("image", "")
        command = svc_def.get("command")
        if isinstance(command, str):
            command = command.split()

        environment = _parse_environment(svc_def.get("environment", {}))

        # Ports from docker-compose
        ports: list[PortSpec] = []
        for port_entry in svc_def.get("ports", []):
            container_port = _parse_port(port_entry)
            ports.append(PortSpec(container_port=container_port))

        # Overlay the registry-level port as the service port
        if svc_name in app.services:
            registry_port = int(app.services[svc_name])
            if ports:
                ports[0] = PortSpec(
                    container_port=ports[0].container_port,
                    port=registry_port,
                )
            else:
                ports.append(PortSpec(container_port=registry_port, port=registry_port))

        # Volumes from docker-compose as pass-through dict
        volumes: dict[str, str] = {}
        for vol in svc_def.get("volumes", []):
            if isinstance(vol, str) and ":" in vol:
                parts = vol.split(":", 1)
                volumes[parts[0]] = parts[1]

        svc_spec = AppServiceSpec(
            name=svc_name,
            image=image,
            command=command,
            environment=environment,
            ports=ports,
            volumes=volumes,
            security_context=app.security_context,
        )
        svc_specs.append(svc_spec)

    return HelxAppSpec(app_class_name=app.app_id, services=svc_specs)


def build_helxinst_spec(
    app: ResolvedApp,
    username: str,
    resource_request: dict | None = None,
    security_context: SecurityContext | None = None,
) -> HelxInstSpec:
    """Build a HelxInst spec for a user's launch request.

    :param app: The resolved app from the registry.
    :param username: The requesting user.
    :param resource_request: Resource dict, e.g.
        ``{"cpu": "2", "memory": "4Gi", "gpu": "1"}``.
    :param security_context: Instance-level override; falls back to
        app-level if not provided.
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
    )


def _parse_environment(env: dict | list) -> dict[str, str]:
    """Normalize docker-compose environment to a dict."""
    if isinstance(env, dict):
        return {k: str(v) for k, v in env.items()}
    if isinstance(env, list):
        result: dict[str, str] = {}
        for item in env:
            if "=" in item:
                k, v = item.split("=", 1)
                result[k] = v
            else:
                result[item] = ""
        return result
    return {}


def _parse_port(port_entry: str | int | dict) -> int:
    """Extract the container port from a docker-compose port entry."""
    if isinstance(port_entry, int):
        return port_entry
    if isinstance(port_entry, dict):
        return int(port_entry.get("target", port_entry.get("containerPort", 0)))
    # String like "8888:8888" or "8888"
    s = str(port_entry)
    if ":" in s:
        return int(s.rsplit(":", 1)[-1])
    return int(s)
