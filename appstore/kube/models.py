"""
Data models for the kube library.

Maps to the helxapp-controller CRD types: HelxApp, HelxInst, HelxUser.
Also provides response types compatible with the existing TychoContext
interface (TychoStatus, TychoSystem, TychoService).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


# -----------------------------------------------------------------------
# CRD spec models
# -----------------------------------------------------------------------

@dataclass
class SecurityContext:
    """Pod or container security context."""

    run_as_user: int | None = None
    run_as_group: int | None = None
    fs_group: int | None = None
    supplemental_groups: list[int] | None = None

    def to_dict(self) -> dict:
        ctx: dict = {}
        if self.run_as_user is not None:
            ctx["runAsUser"] = self.run_as_user
        if self.run_as_group is not None:
            ctx["runAsGroup"] = self.run_as_group
        if self.fs_group is not None:
            ctx["fsGroup"] = self.fs_group
        if self.supplemental_groups:
            ctx["supplementalGroups"] = self.supplemental_groups
        return ctx


@dataclass
class ResourceSpec:
    """CPU / memory / GPU / ephemeral-storage for a single container."""

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    ephemeral_storage: str | None = None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {}
        if self.cpu is not None:
            d["cpu"] = self.cpu
        if self.memory is not None:
            d["memory"] = self.memory
        if self.gpu is not None:
            d["nvidia.com/gpu"] = self.gpu
        if self.ephemeral_storage is not None:
            d["ephemeral-storage"] = self.ephemeral_storage
        return d


@dataclass
class ContainerResources:
    """Request/limit pair for a single container within a HelxInst."""

    request: ResourceSpec = field(default_factory=ResourceSpec)
    limit: ResourceSpec = field(default_factory=ResourceSpec)

    def to_dict(self) -> dict:
        d: dict = {}
        req = self.request.to_dict()
        lim = self.limit.to_dict()
        if req:
            d["request"] = req
        if lim:
            d["limit"] = lim
        return d


@dataclass
class PortSpec:
    """A port pair in a HelxApp service definition."""

    container_port: int
    port: int = 0  # 0 means no Service generated


@dataclass
class AppServiceSpec:
    """One service (container) within a HelxApp spec."""

    name: str
    image: str
    command: list[str] | None = None
    environment: dict[str, str] = field(default_factory=dict)
    ports: list[PortSpec] = field(default_factory=list)
    volumes: dict[str, str] = field(default_factory=dict)
    secrets_from: list[str] = field(default_factory=list)
    init: bool = False
    resource_bounds: dict | None = None
    security_context: SecurityContext | None = None

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "image": self.image}
        if self.command:
            d["command"] = self.command
        if self.environment:
            d["environment"] = self.environment
        if self.secrets_from:
            d["secretsFrom"] = list(self.secrets_from)
        if self.ports:
            d["ports"] = [
                {"containerPort": p.container_port, "port": p.port}
                for p in self.ports
            ]
        if self.volumes:
            d["volumes"] = self.volumes
        if self.init:
            d["init"] = True
        if self.resource_bounds:
            d["resourceBounds"] = self.resource_bounds
        if self.security_context:
            d["securityContext"] = self.security_context.to_dict()
        return d


@dataclass
class HelxAppSpec:
    """Spec for a HelxApp CRD."""

    app_class_name: str
    services: list[AppServiceSpec] = field(default_factory=list)
    helx_vars: list[str] | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "appClassName": self.app_class_name,
            "services": [s.to_dict() for s in self.services],
        }
        if self.helx_vars:
            d["helxVars"] = self.helx_vars
        return d


@dataclass
class HelxInstSpec:
    """Spec for a HelxInst CRD — a per-user instantiation request."""

    app_name: str
    user_name: str
    resources: dict[str, ContainerResources] = field(default_factory=dict)
    security_context: SecurityContext | None = None
    environment: dict[str, str] | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "appName": self.app_name,
            "userName": self.user_name,
        }
        if self.environment:
            d["environment"] = self.environment
        if self.resources:
            d["resources"] = {
                name: cr.to_dict() for name, cr in self.resources.items()
            }
        if self.security_context:
            d["securityContext"] = self.security_context.to_dict()
        return d


@dataclass
class HelxUserSpec:
    """Spec for a HelxUser CRD.

    Fields map to the helxapp-controller HelxUser spec:
      - userHandle: optional URL for security-context resolution
      - environment: user-level env vars (merged between app and instance)
      - volumes: user-level volumes (volume DSL strings, mounted on all containers)
    """

    user_handle: str | None = None
    environment: dict[str, str] | None = None
    volumes: dict[str, str] | None = None

    def to_dict(self) -> dict:
        d: dict = {}
        if self.user_handle:
            d["userHandle"] = self.user_handle
        if self.environment:
            d["environment"] = self.environment
        if self.volumes:
            d["volumes"] = self.volumes
        return d


# -----------------------------------------------------------------------
# Status / response models (compatible with TychoContext interface)
# -----------------------------------------------------------------------

@dataclass
class InstanceStatus:
    """Status of a running instance, read from derived Deployments."""

    name: str
    instance_id: str
    app_name: str | None = None
    username: str | None = None
    creation_time: str | None = None
    is_ready: bool = False
    replicas: int = 0
    ready_replicas: int = 0
    resource_usage: dict[str, dict[str, str]] = field(default_factory=dict)
    workspace_name: str = ""
