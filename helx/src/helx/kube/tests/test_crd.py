"""Tests for the low-level CRD helpers."""

from unittest.mock import MagicMock

import pytest
from kubernetes.client.rest import ApiException

from helx.kube.crd import create_crd, get_crd, delete_crd, list_crds, update_crd


@pytest.fixture
def mock_api():
    return MagicMock()


class TestCreateCRD:
    def test_creates_with_correct_body(self, mock_api):
        mock_api.create_namespaced_custom_object.return_value = {"metadata": {"name": "x"}}
        result = create_crd(mock_api, "ns", "helxapps", "myapp", {"appClassName": "Foo"})
        call = mock_api.create_namespaced_custom_object.call_args
        body = call.kwargs["body"]
        assert body["apiVersion"] == "helx.renci.org/v1"
        assert body["kind"] == "HelxApp"
        assert body["metadata"]["name"] == "myapp"
        assert body["spec"]["appClassName"] == "Foo"


class TestGetCRD:
    def test_returns_object(self, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {"spec": {}}
        result = get_crd(mock_api, "ns", "helxinsts", "inst1")
        assert result == {"spec": {}}

    def test_returns_none_on_404(self, mock_api):
        mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)
        result = get_crd(mock_api, "ns", "helxinsts", "missing")
        assert result is None

    def test_raises_on_other_error(self, mock_api):
        mock_api.get_namespaced_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(ApiException):
            get_crd(mock_api, "ns", "helxinsts", "bad")


class TestDeleteCRD:
    def test_deletes(self, mock_api):
        delete_crd(mock_api, "ns", "helxusers", "bob")
        mock_api.delete_namespaced_custom_object.assert_called_once_with(
            group="helx.renci.org",
            version="v1",
            namespace="ns",
            plural="helxusers",
            name="bob",
        )


class TestListCRDs:
    def test_returns_items(self, mock_api):
        mock_api.list_namespaced_custom_object.return_value = {
            "items": [{"metadata": {"name": "a"}}, {"metadata": {"name": "b"}}]
        }
        result = list_crds(mock_api, "ns", "helxapps")
        assert len(result) == 2


class TestUpdateCRD:
    def test_replaces_spec(self, mock_api):
        mock_api.get_namespaced_custom_object.return_value = {
            "metadata": {"name": "x", "resourceVersion": "42"},
            "spec": {"old": "data"},
        }
        mock_api.replace_namespaced_custom_object.return_value = {"spec": {"new": "data"}}

        update_crd(mock_api, "ns", "helxapps", "x", {"new": "data"})

        call = mock_api.replace_namespaced_custom_object.call_args
        body = call.kwargs["body"]
        assert body["spec"] == {"new": "data"}
