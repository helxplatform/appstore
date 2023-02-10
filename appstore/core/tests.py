import logging

from core.admin_tests import *
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
