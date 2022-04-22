import logging
import os
from dataclasses import dataclass, InitVar, field

logger = logging.getLogger(__name__)


@dataclass
class Resources:
    cpus: float
    gpus: int
    memory: str


@dataclass
class App:
    """Tycho app attributes."""

    name: str
    app_id: str
    description: str
    detail: str
    docs: str
    spec: str
    count: int
    minimum_resources: dict
    maximum_resources: dict


@dataclass
class Instance:
    """Tycho instance attributes."""

    name: str
    docs: str
    aid: str
    sid: str
    fqsid: str
    workspace_name: str
    creation_time: str
    cpus: float
    gpus: int
    memory: float
    host: InitVar[str]
    username: InitVar[str]
    url: str = field(init=False)
    status: str = field(init=False)
    protocol: InitVar[str] = os.environ.get("ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http")

    def __post_init__(self, host, username, protocol):
        # TODO use urllib to confirm construction of a valid resource path
        # http://0.0.0.0:8000/private/jupyter-ds/admin/018b22862f8b44858cca6ad84430b364
        self.url = (
            f"{self.protocol}://{host}/private/{self.aid}/" f"{username}/{self.sid}/"
        )

        # Would be better to get this from tycho per app based on the pod status
        # in kubernetes. That could then be provided via the rest endpoint to a
        # client, or using sockets a notification on pod status change.
        if self.aid is None or "None" in self.url:
            self.status = "starting"
        else:
            self.status = "ready"

        logger.debug(f"{self.name} app-networking constructed url: {self.url}")


@dataclass
class ResourceRequest:
    """Resource request spec."""

    app_id: str
    cpus: float
    gpus: int
    memory: str
    resources: dict = None

    def __post_init__(self):
        self.resources = {
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": self.cpus,
                        "memory": self.memory,
                        "gpus": self.gpus,
                    },
                    "reservations": {
                        "cpus": self.cpus,
                        "memory": self.memory,
                        "gpus": self.gpus,
                    },
                }
            }
        }


@dataclass
class InstanceSpec:
    """App instance spec submitted to tycho."""

    username: str
    app_id: str
    name: str
    host: str
    resources: dict
    ip: InitVar[str]
    port: InitVar[int]
    svc_id: InitVar[str]
    sys_id: InitVar[str]
    url: str = field(init=False)
    sid: str = field(init=False)
    protocol: str = os.environ.get("ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http")

    def __post_init__(self, ip, port, svc_id, sys_id):
        logger.debug(f"Finishing spec construction.")

        if ip:
            self.url = f"http://{ip}:{port}"
        elif sys_id:
            self.url = (
                f"{self.protocol}://{self.host}/private/{self.app_id}/"
                f"{self.username}/{sys_id}/"
            )
        else:
            self.url = (
                f"{self.protocol}://{self.host}/private/{self.app_id}/"
                f"{self.username}/{svc_id}/"
            )
        self.sid = sys_id
        logger.debug(f"-- app-networking constructed url: {self.url}")


@dataclass
class LoginProvider:
    """Login provider attributes."""

    name: str
    url: str

@dataclass
class User:
    REMOTE_USER: str
    ACCESS_TOKEN: str
    SESSION_TIMEOUT: int