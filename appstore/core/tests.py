import logging
from unittest.mock import Mock, patch

from core.admin_tests import *   # noqa: F403
from django.http import HttpResponse, HttpResponseRedirect

logger = logging.getLogger(__name__)


class DictObjects:
    def __init__(self, **data):
        self.__dict__.update(data)


class AppTests(TestCase):
    """
    Test urls, views, and interfaces to application management infrastructure.
    """

    def setUp(self):
        self.data = {'ip_address': 'x.y.z', 'port': '9090', 'identifier': '123456'}
        self.service = DictObjects(**self.data)
        """ Create SuperUser """
        self.superuser = User.objects.create_superuser(username='admin', email="admin@admin.com", password='admin')

    def test_auth_loggedin_admin_user(self):
        """Test the auth endpoint for a logged in User"""
        logger.info(f'{"-- testing auth endpoint for logged in admin user"}')
        credentials = {'username': 'admin', 'password': 'admin'}
        self.client.login(**credentials)
        response = self.client.get("/auth/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, HttpResponse))
        access_token = response.headers.get("ACCESS_TOKEN")
        self.assertEqual(access_token, "")
        remote_user = response.headers.get("REMOTE_USER")
        self.assertEqual(remote_user, "admin")

    def test_auth_nonloggedin_user(self):
        logger.info(f'{"-- testing auth endpoint for non logged in user"}')
        response = self.client.get("/auth/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, "/accounts/login?next=/auth/")

    def test_auth_normalizes_remote_user_to_lowercase(self):
        mixed_user = User.objects.create_superuser(
            username="waTeim",
            email="wateim@example.com",
            password="admin2",
        )
        self.client.login(username="waTeim", password="admin2")

        response = self.client.get("/auth/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("REMOTE_USER"), "wateim")
        mixed_user.delete()

    @patch("core.views._get_helxinst_manager")
    def test_private_route_redirects_guid_to_controller_uuid(self, mock_get_helxinst_manager):
        mock_mgr = Mock()
        mock_mgr.get.return_value = {"status": {"uuid": "3ccf4b07-ea15-488e-9208-48b0e3ffbb53"}}
        mock_get_helxinst_manager.return_value = mock_mgr

        response = self.client.get("/private/pgadmin/wateim/4ec0678656034b7198ae30fa598196af")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "/private/pgadmin/wateim/3ccf4b07-ea15-488e-9208-48b0e3ffbb53/",
        )

    @patch("core.views._get_helxinst_manager")
    def test_private_route_returns_404_when_no_matching_helxinst(self, mock_get_helxinst_manager):
        mock_mgr = Mock()
        mock_mgr.get.return_value = None
        mock_get_helxinst_manager.return_value = mock_mgr

        response = self.client.get("/private/pgadmin/wateim/missing-guid/")

        self.assertEqual(response.status_code, 404)
