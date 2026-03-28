"""Tests for HelxInstManager."""

from unittest.mock import MagicMock

import pytest
from kubernetes.client.rest import ApiException

from kube.exceptions import InstanceError
from kube.helxinsts import HelxInstManager
from kube.models import ContainerResources, HelxInstSpec, ResourceSpec, SecurityContext


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def manager(mock_api):
    return HelxInstManager(custom_api=mock_api, namespace="test-ns")


class TestCreate:
    def test_create_triggers_workload(self, manager, mock_api):
        mock_api.create_namespaced_custom_object.return_value = {}
        spec = HelxInstSpec(
            app_name="jupyterlab",
            user_name="jeffw",
            resources={
                "main": ContainerResources(
                    request=ResourceSpec(cpu="2", memory="1G"),
                    limit=ResourceSpec(cpu="2", memory="1.1G"),
                )
            },
        )
        manager.create("jupyterlab-jeffw", spec)
        call = mock_api.create_namespaced_custom_object.call_args
        body = call.kwargs["body"]
        assert body["spec"]["appName"] == "jupyterlab"
        assert body["spec"]["userName"] == "jeffw"
        assert body["spec"]["resources"]["main"]["limit"]["memory"] == "1.1G"


class TestDelete:
    def test_delete(self, manager, mock_api):
        manager.delete("jupyterlab-jeffw")
        mock_api.delete_namespaced_custom_object.assert_called_once()

    def test_delete_error(self, manager, mock_api):
        mock_api.delete_namespaced_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(InstanceError):
            manager.delete("bad")


class TestUpdate:
    def test_update_resources(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {
            "metadata": {"name": "inst1"},
            "spec": {"appName": "app", "userName": "bob"},
        }
        mock_api.replace_namespaced_custom_object.return_value = {}
        spec = HelxInstSpec(
            app_name="app",
            user_name="bob",
            resources={"main": ContainerResources(limit=ResourceSpec(cpu="4"))},
        )
        manager.update("inst1", spec)
        call = mock_api.replace_namespaced_custom_object.call_args
        body = call.kwargs["body"]
        assert body["spec"]["resources"]["main"]["limit"]["cpu"] == "4"


class TestGetUUID:
    def test_returns_uuid(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {
            "status": {"uuid": "abc-123"}
        }
        assert manager.get_uuid("inst1") == "abc-123"

    def test_returns_none_when_missing(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)
        assert manager.get_uuid("missing") is None

    def test_returns_none_when_no_status(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {"spec": {}}
        assert manager.get_uuid("no-status") is None
