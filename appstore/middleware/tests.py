from django.conf import settings
from django.contrib.auth.models import User, Group
from django.http import HttpResponseRedirect
from django.test import TestCase
from mock import Mock
from core.models import AuthorizedUser
from middleware.filter_whitelist_middleware import AllowWhiteListedUserOnly


class AllowWhiteListedUserOnlyTests(TestCase):
    """ Test the authorization filter middleware. """

    def setUp(self):
        """ Configure the authorization filter. """
        self.middleware = AllowWhiteListedUserOnly()
        self.request = Mock()
        self.request.META = {
            "HTTP_REMOTE_USER": "testuser",
            "REQUEST_METHOD": "POST",
            "HTTP_OPERATING_SYSTEM_VERSION": "ICE CREAM",
            "HTTP_PLATFORM": "ANDROID",
            "HTTP_APP_VERSION": "1.0.0",
            "HTTP_USER_AGENT": "AUTOMATED TEST"
        }
        self.request.scheme = 'http'
        self.request.path = '/apps/'
        self.request.session = {}
        self.groups = Group.objects.create(name='whitelisted')

    def test_request_processing(self):
        """ Test processing a request. """
        self.client.login(username='admin', password='adminx')
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def _create_user_and_login(self, username='test', email='test@test.com', passowrd='admin'):
        """Test for creating user"""
        user = User.objects.create(username=username, email=email)
        user.set_password(passowrd)
        user.save()
        self.client.login(usernam=username, password=passowrd)
        return user

    def test_login_whitelisted_user(self):
        user = self._create_user_and_login(username='Steve_whitelist', email='steve@renci.com', passowrd='admin')
        AuthorizedUser.objects.create(email=user.email)
        self.request.user = user
        self.request.session = self.client.session
        response = self.middleware.process_request(self.request)
        self.assertEqual(list(self.request.user.groups.values_list('name', flat=True))[0], self.groups.name)

    def test_redirect_non_whitelisted_user(self):
        user = self._create_user_and_login(username='Steve_nonwhitelist', email='steve@non-whitelestd.com',
                                           passowrd='admin')
        self.request.user = user
        self.request.session = self.client.session
        response = self.middleware.process_request(self.request)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, settings.LOGIN_WHITELIST_URL)
