"""Tests for security context resolution."""

from unittest.mock import patch, MagicMock

import pytest

from kube.exceptions import SecurityContextError
from kube.models import SecurityContext
from kube.security import resolve_security_context


class TestResolveSecurityContext:
    def test_instance_override_wins(self):
        override = SecurityContext(run_as_user=1000, fs_group=2000)
        result = resolve_security_context(
            instance_override=override,
            user_handle_url="http://should-not-be-called",
        )
        assert result is override

    def test_no_override_no_url_returns_none(self):
        result = resolve_security_context()
        assert result is None

    @patch("kube.security.requests.get")
    def test_user_handle_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "runAsUser": 1001,
            "runAsGroup": 1001,
            "fsGroup": 2001,
            "supplementalGroups": [3000, 4000],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = resolve_security_context(
            user_handle_url="http://ldap/user/bob"
        )
        assert result.run_as_user == 1001
        assert result.run_as_group == 1001
        assert result.fs_group == 2001
        assert result.supplemental_groups == [3000, 4000]
        mock_get.assert_called_once_with("http://ldap/user/bob", timeout=5.0)

    @patch("kube.security.requests.get")
    def test_user_handle_url_failure(self, mock_get):
        mock_get.side_effect = ConnectionError("refused")
        with pytest.raises(SecurityContextError, match="Failed to fetch"):
            resolve_security_context(
                user_handle_url="http://bad-host/user/x"
            )
