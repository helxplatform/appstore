from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User, Group
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.test import TestCase, Client

from mock import Mock

from core.models import AuthorizedUser

from middleware.filter_whitelist_middleware import AllowWhiteListedUserOnly
from middleware.authorized_user import AuthorizedUserCheck


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
            "HTTP_USER_AGENT": "AUTOMATED TEST",
            "HTTP_HOST": "localhost",
        }
        self.request.scheme = "http"
        self.request.path = "/apps/"
        self.request.session = {}
        self.groups = Group.objects.create(name="whitelisted")

    def test_request_processing(self):
        """ Test processing a request. """
        self.client.login(username="admin", password="adminx")
        response = self.middleware.process_request(self.request)
        self.assertIsNone(response)

    def _create_user_and_login(
        self, username="test", email="test@test.com", password="admin"
    ):
        """Test for creating user"""
        user = User.objects.create(username=username, email=email)
        user.set_password(password)
        user.save()
        self.client.login(username=username, password=password)
        return user

    def test_login_whitelisted_user(self):
        user = self._create_user_and_login(
            username="Steve_whitelist", email="steve@renci.com", password="admin"
        )
        AuthorizedUser.objects.create(email=user.email)
        self.request.user = user
        self.request.session = self.client.session
        response = self.middleware.process_request(self.request)
        self.assertEqual(
            list(self.request.user.groups.values_list("name", flat=True))[0],
            self.groups.name,
        )

    def test_redirect_non_whitelisted_user(self):
        user = self._create_user_and_login(
            username="Steve_nonwhitelist",
            email="steve@non-whitelestd.com",
            password="admin",
        )
        self.request.user = user
        self.request.session = self.client.session
        response = self.middleware.process_request(self.request)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, settings.LOGIN_WHITELIST_URL)


class AllowAuthorizedUserOnlyTests(TestCase):
    """
    Test the user authorization filter middleware.
    """

    def setUp(self):
        groups = Group.objects.create(name="whitelisted")
        groups.save()

    @contextmanager
    def _create_user(self, *, username, email, password, super=False):
        if super:
            user = User.objects.create_superuser(username=username)
        else:
            user = User.objects.create(username=username, email=email)
        user.set_password(password)
        user.save()
        try:
            yield user
        finally:
            stale = User.objects.get(username=user.username)
            stale.delete()
            stale.save()

    @contextmanager
    def _add_user_to_authorized_users(self, *, email):
        auth = AuthorizedUser.objects.create(email=email)
        auth.save()
        try:
            yield auth
        finally:
            stale = AuthorizedUser.objects.get(email=email)
            stale.delete()
            stale.save()

    def test_super_user_request_processing(self):
        username = "new_admin"
        email = "new_admin@a_domain.com"
        password = "jhW8*7!AZXPs3Q*TPczJ3TeBqkRSZ*GM"

        with self.modify_settings(
            MIDDLEWARE={
                "append": "middleware.authorized_user.AuthorizedUserCheck",
                "remove": [
                    "middleware.filter_whitelist_middleware.AllowWhiteListedUserOnly"
                ],
            }
        ):
            with self._create_user(
                username=username, email=email, password=password, super=True
            ) as user:
                client = Client()
                client.login(username=username, password=password)
                response = client.get("/apps/")
                self.assertEqual(response.status_code, 200)

                response = client.get("/api/v1/apps/")
                self.assertEqual(response.status_code, 200)

    def test_login_authorized_user(self):
        username = "authorized_user_test"
        email = "authorized_user_test@a_domain.com"
        password = "puyrKA%!4fmE8WU3zwJrF9z!jCauhKVw"

        with self.modify_settings(
            MIDDLEWARE={
                "append": "middleware.authorized_user.AuthorizedUserCheck",
                "remove": [
                    "middleware.filter_whitelist_middleware.AllowWhiteListedUserOnly"
                ],
            }
        ):
            with self._create_user(
                username=username, email=email, password=password
            ) as user:
                with self._add_user_to_authorized_users(email=email):
                    client = Client()
                    client.login(username=username, password=password)
                    response = client.get("/apps/")
                    self.assertEqual(response.status_code, 200)

                    response = client.get("/api/v1/apps/")
                    self.assertEqual(response.status_code, 200)

    def test_raise_403_for_unauthorized_user(self):
        username = "unauthorized_user_test"
        email = "unauthorized_user_test@a_domain.com"
        password = "puyrKA%!4fmE8WU3zwJrF9z!jCauhKVw"

        with self.modify_settings(
            MIDDLEWARE={
                "append": "middleware.authorized_user.AuthorizedUserCheck",
                "remove": [
                    "middleware.filter_whitelist_middleware.AllowWhiteListedUserOnly"
                ],
            }
        ):
            with self._create_user(
                username=username, email=email, password=password
            ) as user:
                client = Client()
                client.login(username=username, password=password)

                response = client.get("/apps/")
                self.assertEqual(response.status_code, 403)

                response = client.get("/api/v1/apps/")
                self.assertEqual(response.status_code, 403)