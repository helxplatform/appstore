"""
Label constants and helpers aligned with helxapp-controller taxonomy.

helxapp-controller labels use the ``helx.renci.org`` prefix.  This module
provides constants for those keys plus helpers to build label dicts and
Kubernetes label-selector strings.
"""

# --- Label key constants ------------------------------------------------

PREFIX = "helx.renci.org"

ID = f"{PREFIX}/id"
APP_NAME = f"{PREFIX}/app-name"
USERNAME = f"{PREFIX}/username"
APP_CLASS_NAME = f"{PREFIX}/app-class-name"
INSTANCE_NAME = f"{PREFIX}/instance-name"
RETAIN = f"{PREFIX}/retain"

EXECUTOR = "executor"
EXECUTOR_VALUE = "helxapp-controller"

# Legacy tycho labels (for backward-compatible queries)
TYCHO_GUID = "tycho-guid"
TYCHO_EXECUTOR_VALUE = "tycho"


def standard_labels(
    instance_id: str,
    app_name: str | None = None,
    username: str | None = None,
    app_class_name: str | None = None,
    instance_name: str | None = None,
) -> dict[str, str]:
    """Build the standard label dict applied to all derived objects.

    :param instance_id: UUID identifying this instance.
    :param app_name: Logical application name.
    :param username: Owning user.
    :param app_class_name: Application class (e.g. "JupyterLab").
    :param instance_name: CRD instance name.
    """
    labels: dict[str, str] = {
        EXECUTOR: EXECUTOR_VALUE,
        ID: instance_id,
    }
    if app_name is not None:
        labels[APP_NAME] = app_name
    if username is not None:
        labels[USERNAME] = username
    if app_class_name is not None:
        labels[APP_CLASS_NAME] = app_class_name
    if instance_name is not None:
        labels[INSTANCE_NAME] = instance_name
    return labels


def selector_by_id(instance_id: str) -> str:
    """Return a label-selector string that matches a specific instance UUID."""
    return f"{ID}={instance_id}"


def selector_by_username(username: str) -> str:
    """Return a label-selector string matching all objects for a user."""
    return f"{USERNAME}={username}"


def selector_all_managed() -> str:
    """Return a label-selector matching all objects managed by the controller."""
    return f"{EXECUTOR}={EXECUTOR_VALUE}"
