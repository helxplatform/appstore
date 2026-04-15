"""Tests for StatusQuery — reading derived Deployments."""

from unittest.mock import MagicMock
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from helx.kube import labels as L
from helx.kube.exceptions import StatusError
from helx.kube.status import StatusQuery


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def query(mock_api):
    return StatusQuery(apps_api=mock_api, namespace="test-ns")


def _make_deployment(
    name, controller_uuid, username, app_name="jupyter",
    instance_name=None, ready=True, guid=None, reference_id=None,
):
    """Build a mock Deployment object.

    :param controller_uuid: The UUID assigned by the controller (helx.renci.org/id).
    :param instance_name: The HelxInst CR name (helx.renci.org/instance-name).
        Defaults to ``name`` if not provided.
    """
    item = MagicMock()
    item.metadata.name = name
    item.metadata.labels = {
        L.ID: controller_uuid,
        L.USERNAME: username,
        L.APP_NAME: app_name,
        L.INSTANCE_NAME: instance_name or name,
        L.EXECUTOR: L.EXECUTOR_VALUE,
    }
    item.metadata.creation_timestamp = datetime(
        2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc
    )
    item.status.replicas = 1
    item.status.ready_replicas = 1 if ready else 0

    container = MagicMock()
    container.name = "main"
    container.resources.limits = {"cpu": "2", "memory": "4Gi"}
    container.env = []
    if reference_id is not None:
        container.env.append(SimpleNamespace(name="REFERENCE_ID", value=reference_id))
    if guid is not None:
        container.env.append(SimpleNamespace(name="GUID", value=guid))
    item.spec.template.spec.containers = [container]
    return item


class TestInstanceIdExtraction:
    """The appstore instance_id comes from GUID env when available,
    otherwise it falls back to label-based extraction."""

    def test_prefers_guid_env_when_present(self, query, mock_api):
        dep = _make_deployment(
            "jupyter-controller-uuid-deploy", "controller-uuid-999",
            "alice", app_name="jupyter",
            instance_name="jupyter-controller-uuid-999",
            guid="abc123",
        )
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_username("alice")
        assert len(results) == 1
        assert results[0].instance_id == "abc123"

    def test_prefers_reference_id_env_when_present(self, query, mock_api):
        dep = _make_deployment(
            "jupyter-controller-uuid-deploy", "controller-uuid-999",
            "alice", app_name="jupyter",
            instance_name="jupyter-controller-uuid-999",
            reference_id="ref-abc123",
            guid="legacy-guid-ignored",
        )
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_username("alice")
        assert len(results) == 1
        assert results[0].instance_id == "ref-abc123"

    def test_extracts_from_instance_name(self, query, mock_api):
        dep = _make_deployment(
            "jupyter-abc123-deploy", "ctrl-uuid-999",
            "alice", app_name="jupyter",
            instance_name="jupyter-abc123",
        )
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_username("alice")
        assert len(results) == 1
        assert results[0].instance_id == "abc123"

    def test_fallback_to_instance_name_when_no_app_prefix(self, query, mock_api):
        dep = _make_deployment(
            "deploy-x", "ctrl-uuid", "alice",
            app_name="", instance_name="deploy-x",
        )
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_username("alice")
        assert results[0].instance_id == "deploy-x"


class TestByInstanceId:
    def test_filters_by_appstore_instance_id(self, query, mock_api):
        deps = [
            _make_deployment(
                "jupyter-abc-deploy", "ctrl-1", "alice",
                instance_name="jupyter-abc",
            ),
            _make_deployment(
                "jupyter-xyz-deploy", "ctrl-2", "alice",
                instance_name="jupyter-xyz",
            ),
        ]
        mock_api.list_namespaced_deployment.return_value.items = deps

        results = query.by_instance_id("abc")
        assert len(results) == 1
        assert results[0].instance_id == "abc"

        # Queries all managed deployments (not by helx.renci.org/id)
        mock_api.list_namespaced_deployment.assert_called_with(
            namespace="test-ns",
            label_selector=f"executor={L.EXECUTOR_VALUE}",
        )

    def test_filters_by_guid_env_when_controller_uses_different_uuid(self, query, mock_api):
        deps = [
            _make_deployment(
                "jupyter-controller-a-deploy", "ctrl-1", "alice",
                instance_name="jupyter-controller-a",
                guid="appstore-guid-1",
            ),
            _make_deployment(
                "jupyter-controller-b-deploy", "ctrl-2", "alice",
                instance_name="jupyter-controller-b",
                guid="appstore-guid-2",
            ),
        ]
        mock_api.list_namespaced_deployment.return_value.items = deps

        results = query.by_instance_id("appstore-guid-2")
        assert len(results) == 1
        assert results[0].instance_id == "appstore-guid-2"

    def test_returns_empty_when_not_found(self, query, mock_api):
        mock_api.list_namespaced_deployment.return_value.items = []
        results = query.by_instance_id("nonexistent")
        assert results == []


class TestByControllerId:
    def test_filters_by_controller_uuid_label(self, query, mock_api):
        dep = _make_deployment(
            "pgadmin-controller-deploy", "ctrl-123", "alice",
            instance_name="pgadmin-appstore-guid",
            guid="appstore-guid",
        )
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_controller_id("ctrl-123")
        assert len(results) == 1
        assert results[0].instance_id == "appstore-guid"
        mock_api.list_namespaced_deployment.assert_called_with(
            namespace="test-ns",
            label_selector=f"{L.ID}=ctrl-123",
        )


class TestByUsername:
    def test_returns_all_user_instances(self, query, mock_api):
        deps = [
            _make_deployment(
                "jupyter-id1-deploy", "ctrl-1", "alice",
                instance_name="jupyter-id1",
            ),
            _make_deployment(
                "jupyter-id2-deploy", "ctrl-2", "alice",
                instance_name="jupyter-id2",
            ),
        ]
        mock_api.list_namespaced_deployment.return_value.items = deps

        results = query.by_username("alice")
        assert len(results) == 2
        mock_api.list_namespaced_deployment.assert_called_with(
            namespace="test-ns",
            label_selector="helx.renci.org/username=alice",
        )


class TestNotReady:
    def test_not_ready_deployment(self, query, mock_api):
        dep = _make_deployment(
            "jupyter-x-deploy", "ctrl-x", "bob",
            instance_name="jupyter-x", ready=False,
        )
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_username("bob")
        assert results[0].is_ready is False


class TestApiError:
    def test_raises_status_error(self, query, mock_api):
        mock_api.list_namespaced_deployment.side_effect = ApiException(status=500)
        with pytest.raises(StatusError):
            query.all_managed()
