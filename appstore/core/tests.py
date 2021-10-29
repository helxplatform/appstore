import logging

from core.admin_tests import *
from core.views import form_service_url
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

    def test_app_list(self):
        """ Test listing running apps. """
        logger.info(f"-- testing app list")
        credentials = {'username': 'admin', 'password': 'admin'}
        self.client.login(**credentials)
        response = self.client.get('/apps/')
        self.assertEqual(response.status_code, 200)
        logger.info(f"-- response.context {response.context}")

    def test_app_start(self):
        """ Test starting an app. """
        logger.info(f"-- testing app start")
        response = self.client.get('/start?app_id=x&cpu=0.5&gpu=0&memory=2G')
        self.assertEqual(response.status_code, 301)

    def test_app_delete(self):
        """ Test deleting a running app. """
        logger.info(f"-- testing app delete")
        response = self.client.post("/list_pods/", {
            "id": "xyz",
            'action': 'delete'
        })
        self.assertEqual(response.status_code, 302)

    def test_auth_loggedin_admin_user(self):
        """Test the auth endpoint for a logged in User"""
        logger.info(f"-- testing auth endpoint for logged in admin user")
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
        logger.info(f"-- testing auth endpoint for non logged in user")
        response = self.client.get("/auth/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, "/accounts/login?next=/auth/")

    def test_form_service_url(self):
        """Testing the form service url by passing mock data."""
        url = form_service_url(host="127.0.0.1", app_id='x', service=self.service, username='admin')
        logger.info(f"---- Testing form-service_url{url}")
        self.assertEqual(url, 'http://x.y.z:9090')

    def test_prob_service(self):
        logger.info("---Test Prob URL")
        response = self.client.get("/probe/?url=127.0.0.0:31242")
        self.assertEqual(response.json()['status'], 'fail')
