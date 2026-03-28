"""
Volume DSL parser aligned with the helxapp-controller specification.

Syntax::

    [scheme://]src:mountPath[#subPath][,option[=value]...]

Schemes: ``pvc`` (default), ``nfs``
Options: ``retain``, ``rwx``, ``rox``, ``rwop``, ``size=X``,
         ``storageClass=X``, ``ro``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kube.exceptions import VolumeDSLError

_ACCESS_MODE_MAP = {
    "rwx": "ReadWriteMany",
    "rox": "ReadOnlyMany",
    "rwop": "ReadWriteOncePod",
}

# Matches  [scheme://]src:mountPath[#subPath][,opts...]
_DSL_RE = re.compile(
    r"^(?:(?P<scheme>[a-z]+)://)?(?P<src>[^:]+):(?P<mount>[^,#]+)"
    r"(?:#(?P<subpath>[^,]+))?"
    r"(?P<opts>(?:,[^,]+)*)$"
)


@dataclass
class ParsedVolume:
    """Result of parsing a single volume DSL string."""

    volume_id: str
    scheme: str = "pvc"
    source: str = ""
    mount_path: str = ""
    sub_path: str | None = None
    access_modes: list[str] = field(default_factory=lambda: ["ReadWriteOnce"])
    storage: str = "1Gi"
    storage_class: str | None = None
    retain: bool = False
    read_only: bool = False

    def to_dsl_string(self) -> str:
        """Re-serialize back to DSL format for embedding in HelxApp specs."""
        parts = []
        if self.scheme != "pvc":
            parts.append(f"{self.scheme}://")
        parts.append(f"{self.source}:{self.mount_path}")
        if self.sub_path:
            parts.append(f"#{self.sub_path}")
        opts = []
        for mode, label in _ACCESS_MODE_MAP.items():
            if label in self.access_modes:
                opts.append(mode)
        if self.retain:
            opts.append("retain")
        if self.read_only:
            opts.append("ro")
        if self.storage != "1Gi":
            opts.append(f"size={self.storage}")
        if self.storage_class:
            opts.append(f"storageClass={self.storage_class}")
        if opts:
            parts.append("," + ",".join(opts))
        return "".join(parts)


def parse_volume_dsl(volume_id: str, dsl: str) -> ParsedVolume:
    """Parse a volume DSL string into a :class:`ParsedVolume`.

    :param volume_id: Key name from the volumes map.
    :param dsl: The DSL string to parse.
    :raises VolumeDSLError: On malformed input.
    """
    m = _DSL_RE.match(dsl.strip())
    if not m:
        raise VolumeDSLError(
            message=f"Invalid volume DSL: {dsl!r}",
            details="Expected [scheme://]src:mountPath[#subPath][,options...]",
        )

    scheme = m.group("scheme") or "pvc"
    source = m.group("src")
    mount_path = m.group("mount")
    sub_path = m.group("subpath") or None
    opts_str = m.group("opts") or ""

    if scheme == "nfs":
        # NFS source may look like //server/export
        source = source.lstrip("/")

    pv = ParsedVolume(
        volume_id=volume_id,
        scheme=scheme,
        source=source,
        mount_path=mount_path,
        sub_path=sub_path,
    )

    for opt in opts_str.split(","):
        opt = opt.strip()
        if not opt:
            continue
        if "=" in opt:
            key, val = opt.split("=", 1)
        else:
            key, val = opt, None

        if key in _ACCESS_MODE_MAP:
            pv.access_modes = [_ACCESS_MODE_MAP[key]]
        elif key == "retain":
            pv.retain = True
        elif key == "ro":
            pv.read_only = True
        elif key == "size" and val:
            pv.storage = val
        elif key == "storageClass" and val:
            pv.storage_class = val
        else:
            raise VolumeDSLError(
                message=f"Unknown volume option: {key!r}",
                details=f"In volume DSL: {dsl!r}",
            )

    return pv


def parse_volumes_map(volumes: dict[str, str]) -> list[ParsedVolume]:
    """Parse a dict of ``{volume_id: dsl_string}`` entries."""
    return [parse_volume_dsl(vid, dsl) for vid, dsl in volumes.items()]
