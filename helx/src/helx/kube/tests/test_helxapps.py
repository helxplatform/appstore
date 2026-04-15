"""Tests for HelxAppManager."""

from unittest.mock import MagicMock

import pytest
from kubernetes.client.rest import ApiException

from helx.kube.exceptions import AppError
from helx.kube.helxapps import HelxAppManager
from helx.kube.models import AppServiceSpec, HelxAppSpec, PortSpec


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def manager(mock_api):
    return HelxAppManager(custom_api=mock_api, namespace="test-ns")


class TestCreate:
    def test_create(self, manager, mock_api):
        mock_api.create_namespaced_custom_object.return_value = {}
        spec = HelxAppSpec(
            app_class_name="JupyterLab",
            services=[
                AppServiceSpec(
                    name="main",
                    image="jupyter/minimal:latest",
                    ports=[PortSpec(container_port=8888, port=8888)],
                )
            ],
        )
        manager.create("jupyterlab", spec)
        mock_api.create_namespaced_custom_object.assert_called_once()

    def test_create_error(self, manager, mock_api):
        mock_api.create_namespaced_custom_object.side_effect = ApiException(status=409)
        spec = HelxAppSpec(app_class_name="X")
        with pytest.raises(AppError):
            manager.create("dup", spec)


class TestGet:
    def test_get_found(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {"spec": {}}
        result = manager.get("jupyterlab")
        assert result is not None

    def test_get_not_found(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)
        result = manager.get("missing")
        assert result is None


class TestEnsure:
    def test_ensure_creates_when_missing(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)
        mock_api.create_namespaced_custom_object.return_value = {"metadata": {"name": "app"}}
        spec = HelxAppSpec(app_class_name="App")
        manager.ensure("app", spec)
        mock_api.create_namespaced_custom_object.assert_called_once()

    def test_ensure_updates_when_exists(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {
            "metadata": {"name": "app"},
            "spec": {"appClassName": "Old"},
        }
        mock_api.replace_namespaced_custom_object.return_value = {}
        spec = HelxAppSpec(app_class_name="New")
        manager.ensure("app", spec)
        mock_api.replace_namespaced_custom_object.assert_called_once()


class TestDelete:
    def test_delete(self, manager, mock_api):
        manager.delete("jupyterlab")
        mock_api.delete_namespaced_custom_object.assert_called_once()

    def test_delete_error(self, manager, mock_api):
        mock_api.delete_namespaced_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(AppError):
            manager.delete("bad")
