"""Typed models for parsed docker-compose app specifications."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VolumeMount:
    """A parsed volume mount from a compose spec."""

    source: str
    mount_path: str
    sub_path: str | None = None
    is_pvc: bool = True
    options: dict[str, str] = field(default_factory=dict)

    def to_dsl_string(self) -> str:
        """Convert to volume DSL format for HelxApp spec."""
        if self.sub_path:
            dsl = f"{self.source}:{self.mount_path}#{self.sub_path}"
        else:
            dsl = f"{self.source}:{self.mount_path}"
        if self.options:
            opts = ",".join(
                f"{k}={v}" if v else k for k, v in self.options.items()
            )
            dsl = f"{dsl},{opts}"
        return dsl


@dataclass
class ProbeSpec:
    """A parsed probe definition from registry ext.kube."""

    probe_type: str  # "exec", "httpGet", "tcpSocket"
    delay: int = 0
    period: int = 10
    threshold: int | None = None

    # exec
    command: list[str] | None = None

    # httpGet
    path: str | None = None
    port: int | str | None = None  # may be a Jinja2 template at parse time
    http_headers: list[dict] | None = None

    # tcpSocket reuses port field


@dataclass
class ResourceBound:
    """Min/max/default range for a single resource type."""

    min: str | None = None
    max: str | None = None
    default_request: str | None = None
    default_limit: str | None = None
    resource_name: str | None = None


@dataclass
class ResourceBounds:
    """Full bounds specification from x-helx-resources.bounds."""

    cpu: ResourceBound | None = None
    memory: ResourceBound | None = None
    gpu: ResourceBound | None = None
    ephemeral_storage: ResourceBound | None = None
    lock: bool = False


@dataclass
class ComposeResources:
    """Resource limits/requests extracted from deploy.resources."""

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    ephemeral_storage: str | None = None


@dataclass
class ComposeService:
    """A single service parsed from a docker-compose spec."""

    name: str
    image: str
    command: list[str] | None = None
    environment: dict[str, str] = field(default_factory=dict)
    ports: list[int] = field(default_factory=list)
    expose: list[int] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    limits: ComposeResources = field(default_factory=ComposeResources)
    requests: ComposeResources = field(default_factory=ComposeResources)
    resource_bounds: ResourceBounds | None = None
    depends_on: list[str] = field(default_factory=list)
    liveness_probe: ProbeSpec | None = None
    readiness_probe: ProbeSpec | None = None


@dataclass
class ComposeApp:
    """The complete parsed result of a docker-compose spec."""

    services: list[ComposeService] = field(default_factory=list)
    helx_vars: list[str] = field(default_factory=list)

    def get_service(self, name: str) -> ComposeService | None:
        for svc in self.services:
            if svc.name == name:
                return svc
        return None
