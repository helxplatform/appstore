import json
import logging
from django.test import TestCase

logger = logging.getLogger (__name__)

class AppTests(TestCase):

    """
    Test urls, views, and interfaces to application management infrastructure.
    """

    def test_app_list(self):
        """ Test listing running apps. """
        logger.info (f"-- testing app list")
        response = self.client.get('/apps/')
        self.assertEqual(response.status_code, 200)
        self.log_context (response)
        
    def test_app_start(self):
        """ Test starting an app. """
        logger.info (f"-- testing app start")
        response = self.client.get('/start?app_id=x')
        self.assertEqual(response.status_code, 301)
        self.log_context (response)

    def test_app_delete(self):
        """ Test deleting a running app. """
        logger.info (f"-- testing app delete")
        response = self.client.post("/list_pods/", {
            "sid" : "xyz"
        })
        self.assertEqual(response.status_code, 302)
        self.log_context (response)

    def log_context(self, response):
        logger.info (f"-- response.context: {response.context}")
        
