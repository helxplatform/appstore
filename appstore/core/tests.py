import logging

from core.admin_tests import *
from core.views import form_service_url

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

    def test_app_list(self):
        """ Test listing running apps. """
        logger.info(f"-- testing app list")
        response = self.client.get('/apps/')
        self.assertEqual(response.status_code, 200)
        logger.info(f"-- response.context {response.context}")

    def test_app_start(self):
        """ Test starting an app. """
        logger.info(f"-- testing app start")
        response = self.client.get('/start?app_id=x')
        self.assertEqual(response.status_code, 301)

    def test_app_delete(self):
        """ Test deleting a running app. """
        logger.info(f"-- testing app delete")
        response = self.client.post("/list_pods/", {
            "id": "xyz",
            'action': 'delete'
        })
        self.assertEqual(response.status_code, 302)

    def test_form_service_url(self):
        """Testing the form service url by passing mock data."""
        url = form_service_url(host="127.0.0.1", app_id='x', service=self.service, username='admin')
        logger.info(f"---- Testing form-service_url{url}")
        self.assertEqual(url, 'http://x.y.z:9090')

    def test_prob_service(self):
        logger.info("---Test Prob URL")
        response = self.client.get("/probe/?url=127.0.0.0:31242")
        self.assertEqual(response.json()['status'], 'fail')
