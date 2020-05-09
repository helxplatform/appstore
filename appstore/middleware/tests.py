from django.test import TestCase
from middleware.filter_whitelist_middleware import AllowWhiteListedUserOnly
from mock import Mock

class AllowWhiteListedUserOnlyTests(TestCase):
    """ Test the authorization filter middleware. """
    
    def setUp(self):
        """ Configure the authorization filter. """
        self.middleware = AllowWhiteListedUserOnly()
        self.request = Mock()
        self.request.META = { 
            "HTTP_REMOTE_USER"              : "testuser",
            "REQUEST_METHOD"                : "POST",
            "HTTP_OPERATING_SYSTEM_VERSION" : "ICE CREAM",
            "HTTP_PLATFORM"                 : "ANDROID",
            "HTTP_APP_VERSION"              : "1.0.0",
            "HTTP_USER_AGENT"               : "AUTOMATED TEST"
        }
        self.request.path = '/apps/'
        self.request.session = {}
        
    def test_request_processing(self):
        """ Test processing a request. """
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

