"""Core parser: docker-compose dict -> ComposeApp."""

from __future__ import annotations

from appspec.exceptions import ParseError
from appspec.models import (
    ComposeApp,
    ComposeResources,
    ComposeService,
    ProbeSpec,
    ResourceBound,
    ResourceBounds,
    VolumeMount,
)


def parse_compose(spec: dict, ext: dict | None = None) -> ComposeApp:
    """Parse a docker-compose dict into a ComposeApp.

    :param spec: Parsed docker-compose YAML (already Jinja2-rendered).
    :param ext: Registry ext dict (contains kube.livenessProbe etc.).
    :raises ParseError: On missing required fields.
    """
    services_dict = spec.get("services")
    if not services_dict:
        raise ParseError("Compose spec has no 'services' key")

    probes = ext.get("kube", {}) if ext else {}

    top_secrets = parse_top_level_secrets(spec.get("secrets", {}))

    services = []
    for name, svc_dict in services_dict.items():
        services.append(parse_service(name, svc_dict, probes, top_secrets))

    helx_vars = spec.get("x-helx-vars", [])

    return ComposeApp(services=services, helx_vars=list(helx_vars))


def parse_service(
    name: str, svc: dict, probes: dict | None = None,
    top_secrets: set[str] | None = None,
) -> ComposeService:
    """Parse a single service dict."""
    image = svc.get("image")
    if not image:
        raise ParseError(f"Service '{name}' has no 'image'")

    command = _parse_command_or_entrypoint(svc)
    environment = parse_environment(svc.get("environment", {}))
    ports = parse_ports(svc.get("ports", []))
    expose = [int(p) for p in svc.get("expose", []) if "{{" not in str(p)]
    volumes = parse_volumes(svc.get("volumes", []))
    depends_on = list(svc.get("depends_on", []))
    secrets = parse_service_secrets(svc.get("secrets", []), top_secrets)

    # Resources: prefer x-helx-resources over deploy.resources
    helx_res = svc.get("x-helx-resources")
    if helx_res is not None:
        resource_bounds = parse_helx_resources(helx_res)
        limits, requests = _bounds_to_compose_resources(resource_bounds)
    else:
        resource_bounds = None
        deploy = svc.get("deploy", {}).get("resources", {})
        limits = parse_resources(deploy.get("limits", {}))
        requests = parse_resources(deploy.get("reservations", {}))

    # Probes
    probes = probes or {}
    liveness_probe = parse_probe(probes.get("livenessProbe"))
    readiness_probe = parse_probe(probes.get("readinessProbe"))

    return ComposeService(
        name=name,
        image=image,
        command=command,
        environment=environment,
        ports=ports,
        expose=expose,
        volumes=volumes,
        limits=limits,
        requests=requests,
        resource_bounds=resource_bounds,
        depends_on=depends_on,
        secrets=secrets,
        liveness_probe=liveness_probe,
        readiness_probe=readiness_probe,
    )


def parse_ports(raw_ports: list) -> list[int]:
    """Extract container ports from compose port entries.

    Skips entries that contain un-rendered Jinja2 templates (``{{ … }}``).
    """
    result = []
    for entry in raw_ports:
        s = str(entry)
        if "{{" in s:
            continue
        try:
            if ":" in s:
                result.append(int(s.rsplit(":", 1)[1]))
            else:
                result.append(int(s))
        except ValueError:
            continue
    return result


def parse_environment(env: dict | list) -> dict[str, str]:
    """Normalize environment to a str->str dict."""
    if isinstance(env, dict):
        return {str(k): str(v) for k, v in env.items()}
    result: dict[str, str] = {}
    for entry in env:
        entry = str(entry)
        if "=" in entry:
            k, v = entry.split("=", 1)
            result[k] = v
        else:
            result[entry] = ""
    return result


def parse_volumes(raw_volumes: list[str]) -> list[VolumeMount]:
    """Parse compose volume strings into VolumeMount objects."""
    result = []
    for raw in raw_volumes:
        raw = str(raw)
        # Strip options suffix (comma-separated after the path portion)
        options: dict[str, str] = {}
        # Options come after the mount_path, separated by commas
        # But we need to parse the main volume spec first

        if raw.startswith("pvc://"):
            remainder = raw[len("pvc://"):]
            # Split source:mount_path,options
            source_part, mount_and_opts = remainder.split(":", 1)
            mount_path, options = _split_mount_options(mount_and_opts)
            # source_part may contain subpath: pvc-name/subpath
            if "/" in source_part:
                source, sub_path = source_part.split("/", 1)
            else:
                source = source_part
                sub_path = None
            result.append(VolumeMount(
                source=source,
                mount_path=mount_path,
                sub_path=sub_path,
                is_pvc=True,
                options=options,
            ))
        else:
            # Plain volume: source:mount_path[,options]
            if ":" in raw:
                source, mount_and_opts = raw.split(":", 1)
                mount_path, options = _split_mount_options(mount_and_opts)
            else:
                source = raw
                mount_path = raw
            result.append(VolumeMount(
                source=source,
                mount_path=mount_path,
                is_pvc=False,
                options=options,
            ))
    return result


def parse_resources(raw: dict) -> ComposeResources:
    """Parse a limits or reservations dict into ComposeResources."""
    gpu = raw.get("gpus")
    if gpu is None:
        gpu = _extract_gpu_from_devices(raw.get("devices", []))
    return ComposeResources(
        cpu=_str_or_none(raw.get("cpus")),
        memory=_str_or_none(raw.get("memory")),
        gpu=_str_or_none(gpu),
        ephemeral_storage=_str_or_none(raw.get("ephemeralStorage")),
    )


def parse_helx_resources(raw: dict) -> ResourceBounds:
    """Parse an x-helx-resources dict into ResourceBounds."""
    bounds_dict = raw.get("bounds", {})

    cpu = _parse_bound(bounds_dict.get("cpu")) if "cpu" in bounds_dict else None
    memory = _parse_bound(bounds_dict.get("memory")) if "memory" in bounds_dict else None
    gpu = _parse_bound(bounds_dict.get("gpu")) if "gpu" in bounds_dict else None
    ephemeral = _parse_bound(bounds_dict.get("ephemeral-storage")) if "ephemeral-storage" in bounds_dict else None

    # Default GPU resource name
    if gpu is not None and gpu.resource_name is None:
        gpu.resource_name = "nvidia.com/gpu"

    return ResourceBounds(
        cpu=cpu,
        memory=memory,
        gpu=gpu,
        ephemeral_storage=ephemeral,
        lock=bool(raw.get("lock", False)),
    )


def parse_resource_bound(raw: dict) -> ResourceBound:
    """Parse a single resource bound dict."""
    return _parse_bound(raw)


def parse_probe(raw: dict | str | None) -> ProbeSpec | None:
    """Parse a probe definition. Returns None for 'none' or absent."""
    if raw is None:
        return None
    if isinstance(raw, str):
        if raw.lower() == "none":
            return None
        raise ParseError(f"Unknown probe value: {raw!r}")

    delay = int(raw.get("delay", 0))
    period = int(raw.get("period", 10))
    threshold = raw.get("threshold")
    if threshold is not None:
        threshold = int(threshold)

    if "cmd" in raw:
        return ProbeSpec(
            probe_type="exec",
            command=list(raw["cmd"]),
            delay=delay,
            period=period,
            threshold=threshold,
        )
    if "httpGet" in raw:
        http = raw["httpGet"]
        return ProbeSpec(
            probe_type="httpGet",
            path=http.get("path"),
            port=_parse_port_or_template(http.get("port")),
            http_headers=http.get("httpHeaders"),
            delay=delay,
            period=period,
            threshold=threshold,
        )
    if "tcpSocket" in raw:
        tcp = raw["tcpSocket"]
        return ProbeSpec(
            probe_type="tcpSocket",
            port=_parse_port_or_template(tcp.get("port")),
            delay=delay,
            period=period,
            threshold=threshold,
        )

    raise ParseError(f"Cannot determine probe type from: {raw!r}")


def parse_top_level_secrets(raw: dict) -> set[str]:
    """Parse the top-level ``secrets:`` block.

    Returns a set of secret names that are declared as ``external: true``.
    Non-external secrets are ignored (they have no K8s equivalent).
    """
    result: set[str] = set()
    for name, defn in raw.items():
        if isinstance(defn, dict) and defn.get("external"):
            result.add(name)
    return result


def parse_service_secrets(
    raw: list, top_secrets: set[str] | None = None,
) -> list[str]:
    """Parse a service-level ``secrets:`` list.

    Supports docker-compose short syntax (plain string) and long syntax
    (dict with ``source`` key).  Only secrets declared as external at the
    top level are included; undeclared names are silently skipped.
    """
    top = top_secrets or set()
    result: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = entry.get("source", "")
        else:
            continue
        if name and name in top:
            result.append(name)
    return result


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _parse_port_or_template(val) -> int | str | None:
    """Parse a port value that may be an int, numeric string, or Jinja2 template.

    Template strings like ``{{ system_port }}`` are preserved as-is for
    later resolution at instance launch time.
    """
    if val is None:
        return None
    s = str(val)
    if "{{" in s:
        return s
    try:
        return int(s)
    except ValueError:
        return s


def _parse_command_or_entrypoint(svc: dict) -> list[str] | None:
    """Extract command/entrypoint; entrypoint takes precedence."""
    raw = svc.get("entrypoint") or svc.get("command")
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return str(raw).split()


def _parse_bound(raw: dict) -> ResourceBound:
    return ResourceBound(
        min=_str_or_none(raw.get("min")),
        max=_str_or_none(raw.get("max")),
        default_request=_str_or_none(raw.get("default_request")),
        default_limit=_str_or_none(raw.get("default_limit")),
        resource_name=raw.get("resource_name"),
    )


def _bounds_to_compose_resources(
    bounds: ResourceBounds,
) -> tuple[ComposeResources, ComposeResources]:
    """Extract default limits/requests from ResourceBounds for backfill."""
    limits = ComposeResources(
        cpu=bounds.cpu.default_limit if bounds.cpu else None,
        memory=bounds.memory.default_limit if bounds.memory else None,
        gpu=bounds.gpu.default_limit if bounds.gpu else None,
        ephemeral_storage=bounds.ephemeral_storage.default_limit if bounds.ephemeral_storage else None,
    )
    requests = ComposeResources(
        cpu=bounds.cpu.default_request if bounds.cpu else None,
        memory=bounds.memory.default_request if bounds.memory else None,
        gpu=bounds.gpu.default_request if bounds.gpu else None,
        ephemeral_storage=bounds.ephemeral_storage.default_request if bounds.ephemeral_storage else None,
    )
    return limits, requests


def _extract_gpu_from_devices(devices: list) -> str | None:
    """Extract GPU count from compose devices list."""
    for dev in devices:
        caps = dev.get("capabilities", [])
        if "gpu" in caps:
            count = dev.get("count")
            return str(count) if count is not None else "1"
    return None


def _split_mount_options(mount_and_opts: str) -> tuple[str, dict[str, str]]:
    """Split '/path,opt1,opt2=val' into ('/path', {'opt1': '', 'opt2': 'val'})."""
    parts = mount_and_opts.split(",")
    mount_path = parts[0]
    options: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            options[k] = v
        else:
            options[part] = ""
    return mount_path, options


def _str_or_none(val) -> str | None:
    if val is None:
        return None
    return str(val)
