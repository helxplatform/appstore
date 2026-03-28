"""Tests for StatusQuery — reading derived Deployments."""

from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest
from kubernetes.client.rest import ApiException

from kube import labels as L
from kube.exceptions import StatusError
from kube.status import StatusQuery


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def query(mock_api):
    return StatusQuery(apps_api=mock_api, namespace="test-ns")


def _make_deployment(name, uuid, username, app_name="jupyter", ready=True):
    item = MagicMock()
    item.metadata.name = name
    item.metadata.labels = {
        L.ID: uuid,
        L.USERNAME: username,
        L.APP_NAME: app_name,
    }
    item.metadata.creation_timestamp = datetime(
        2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc
    )
    item.status.replicas = 1
    item.status.ready_replicas = 1 if ready else 0

    container = MagicMock()
    container.name = "main"
    container.resources.limits = {"cpu": "2", "memory": "4Gi"}
    item.spec.template.spec.containers = [container]
    return item


class TestByInstanceId:
    def test_returns_status(self, query, mock_api):
        dep = _make_deployment("app-abc", "abc", "alice")
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_instance_id("abc")
        assert len(results) == 1
        assert results[0].instance_id == "abc"
        assert results[0].is_ready is True
        assert results[0].username == "alice"
        assert results[0].app_name == "jupyter"

        mock_api.list_namespaced_deployment.assert_called_with(
            namespace="test-ns",
            label_selector="helx.renci.org/id=abc",
        )


class TestByUsername:
    def test_returns_all_user_instances(self, query, mock_api):
        deps = [
            _make_deployment("app1", "id1", "alice"),
            _make_deployment("app2", "id2", "alice"),
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
        dep = _make_deployment("app-x", "x", "bob", ready=False)
        mock_api.list_namespaced_deployment.return_value.items = [dep]

        results = query.by_instance_id("x")
        assert results[0].is_ready is False


class TestApiError:
    def test_raises_status_error(self, query, mock_api):
        mock_api.list_namespaced_deployment.side_effect = ApiException(status=500)
        with pytest.raises(StatusError):
            query.all_managed()
