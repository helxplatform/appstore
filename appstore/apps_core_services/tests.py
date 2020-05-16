import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.test import TestCase
from tycho.context import ContextFactory, Principal

logger = logging.getLogger(__name__)


class AppTests(TestCase):
    """
    Test urls, views, and interfaces to application management infrastructure.
    """

    def setUp(self):
        self.tycho = ContextFactory.get(
            context_type=settings.TYCHO_MODE,
            product=settings.APPLICATION_BRAND)
        self.user = User.objects.create_superuser(username='admin', email="admin@admin.com", password='admin')
        self.app_id = 'jupyter-ds'
        self.app = self.tycho.apps.get(self.app_id)
        self.client.login(username='admin', password='admin')

    def test_app_list(self):
        """ Test listing running apps. """
        logger.info(f"-- testing app list")
        response = self.client.get('/apps/')
        self.assertEqual(response.status_code, 200)
        logger.info(f"-- response.context {response.context['svcs_list']}")

    def app_start(self):
        """ Test starting an app. (Jupyter-ds) """
        logger.info(f"-- testing app start")
        self.principal = Principal('admin')
        self.tycho.start(self.principal, self.app_id)
        response = self.client.get(f'/start?app_id={self.app_id}')
        logger.info(f"test start_app {response.status_code} ")
        self.assertEqual(response.status_code, 301)

    # def app_connect(self):
    #     """ Test starting an app. """
    #     self.services = self.tycho.status({
    #         'username': 'admin'
    #     }).services
    #     for service in self.services:
    #         self.url = form_service_url(self.app_id, service, 'steve')
    #         response = self.client.get(
    #             f'/connect/?url={self.url}&name={self.app.get("name")}&icon={self.app.get("icon", "/static/images/app.png")}')
    #         logger.info(f'Test connect_url {response}')
    #         sleep(30)
    #         self.assertEqual(response.status_code, 301)

    # def app_probe(self):
    #     """ Test starting an app. """
    #     logger.info(f"-- testing probe connection 1")
    #     self.services = self.tycho.status({
    #         'username': 'admin'
    #     }).services
    #     print("======================",self.services)
    #     for service in self.services:
    #         self.url = form_service_url(self.app_id, service, 'admin')
    #         test_output = 'ok'
    #         while True:
    #             response = self.client.get(f'/probe/?url={self.url}')
    #             logger.info(f"response prob {response.json()}")
    #             if response.json()['status'] == test_output:
    #                 break
    #         self.assertEqual(response.json()['status'], test_output)

    def app_delete(self):
        """ Test deleting a running app.1 """

        services = self.tycho.status({
            'username': 'admin'
        }).services
        for service in services:
            response = self.client.post("/list_pods/", {
                "id": service.identifier,
                "action": "delete"
            })
            self.assertTrue(isinstance(response, HttpResponseRedirect))
            self.assertEqual(response.url, '/apps/')

    def test_application_process(self):
        self.app_start()
        # self.app_probe()
        # self.app_connect()
        self.app_delete()
