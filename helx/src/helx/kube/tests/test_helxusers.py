"""Tests for HelxUserManager."""

from unittest.mock import MagicMock

import pytest
from kubernetes.client.rest import ApiException

from helx.kube.exceptions import UserError
from helx.kube.helxusers import HelxUserManager
from helx.kube.models import HelxUserSpec


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def manager(mock_api):
    return HelxUserManager(custom_api=mock_api, namespace="test-ns")


class TestCreate:
    def test_create_with_handle(self, manager, mock_api):
        mock_api.create_namespaced_custom_object.return_value = {}
        spec = HelxUserSpec(user_handle="http://ldap/user/jeffw")
        manager.create("jeffw", spec)
        call = mock_api.create_namespaced_custom_object.call_args
        body = call.kwargs["body"]
        assert body["kind"] == "HelxUser"
        assert body["spec"]["userHandle"] == "http://ldap/user/jeffw"

    def test_create_without_handle(self, manager, mock_api):
        mock_api.create_namespaced_custom_object.return_value = {}
        spec = HelxUserSpec()
        manager.create("bob", spec)
        call = mock_api.create_namespaced_custom_object.call_args
        body = call.kwargs["body"]
        assert body["spec"] == {}


class TestEnsure:
    def test_ensure_creates_when_missing(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)
        mock_api.create_namespaced_custom_object.return_value = {}
        spec = HelxUserSpec(user_handle="http://ldap/user/alice")
        manager.ensure("alice", spec)
        mock_api.create_namespaced_custom_object.assert_called_once()

    def test_ensure_updates_when_exists(self, manager, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {
            "metadata": {"name": "alice"},
            "spec": {},
        }
        mock_api.replace_namespaced_custom_object.return_value = {}
        spec = HelxUserSpec(user_handle="http://ldap/user/alice")
        manager.ensure("alice", spec)
        mock_api.replace_namespaced_custom_object.assert_called_once()


class TestDelete:
    def test_delete(self, manager, mock_api):
        manager.delete("jeffw")
        mock_api.delete_namespaced_custom_object.assert_called_once()

    def test_delete_error(self, manager, mock_api):
        mock_api.delete_namespaced_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(UserError):
            manager.delete("bad")
