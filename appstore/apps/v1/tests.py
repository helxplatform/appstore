import logging

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework.test import APIRequestFactory, force_authenticate


from .views import AppViewSet, ServiceViewSet, UsersViewSet, LoginProviderViewSet, AppContextViewSet


logger = logging.getLogger(__name__)


class TestAppView(TestCase):
    def setUp(self):
        # Create auth user for views using api request factory
        # TODO add regular user and programatically add the user to
        # the allowed list for testing.
        self.username = "app_api_tester"
        self.password = "tykj5r6e4%348#dPfKU7"
        self.user = User.objects.create_superuser(
            self.username, "app-test@renci-example.com", self.password
        )

        self.factory = APIRequestFactory()
        self.view = AppViewSet

    def test_anonymous_cannot_see_view(self):
        list_view = self.view.as_view({"get": "list"})
        response = list_view(self.factory.get(""))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_can_get_app_list(self):
        """
        Auth using force_authenticate
        """
        user = User.objects.get(username=self.username)
        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("")
        force_authenticate(api_request, user=user)
        response = list_view(api_request)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        # Remove test user so it's no laying around with a known password.
        User.objects.get(username=self.username, is_superuser=True).delete()


class TestServiceView(TestCase):
    def setUp(self):
        self.username = "service_api_tester"
        self.password = "h82VBBBRM&c2aH59a*a!"
        self.user = User.objects.create_superuser(
            self.username, "service-test@renci-example.com", self.password
        )

        self.factory = APIRequestFactory()
        self.view = ServiceViewSet

    def test_anonymous_cannot_see_view(self):
        list_view = self.view.as_view({"get": "list"})
        response = list_view(self.factory.get(""))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_can_get_service_list(self):
        user = User.objects.get(username=self.username)
        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("")
        force_authenticate(api_request, user=user)
        response = list_view(api_request)
        self.assertEqual(response.status_code, 200)

    # TODO Add POST and DELETE

    def tearDown(self):
        User.objects.get(username=self.username, is_superuser=True).delete()


class TestUserView(TestCase):
    def setUp(self):
        self.username = "user_api_tester"
        self.password = "suva4p4^5J2R4HVzf*62"
        self.user = User.objects.create_superuser(
            self.username, "user-test@renci-example.com", self.password
        )

        self.factory = APIRequestFactory()
        self.view = UsersViewSet

    def test_anonymous_cannot_see_view(self):
        list_view = self.view.as_view({"get": "list"})
        response = list_view(self.factory.get(""))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_fails_without_token(self):
        user = User.objects.get(username=self.username)
        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("")
        api_request.session = {"REMOTE_USER": self.username}
        force_authenticate(api_request, user=user)
        response = list_view(api_request)
        self.assertEqual(response.status_code, 400)

    def test_logged_in_with_token_can_get_data(self):
        user = User.objects.get(username=self.username)
        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("")
        api_request.session = {
            "REMOTE_USER": self.username,
            "Authorization": "Bearer t6GEUD-DkGzfY-ZGseAu-wPvpFD-989QGj",
        }
        force_authenticate(api_request, user=user)
        response = list_view(api_request)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        User.objects.get(username=self.username, is_superuser=True).delete()


class TestLoginProviderView(TestCase):
    def test_anonymous_can_see_view(self):
        """
        This view is required by a front end to know how the user
        can login. Since this happens prior to auth make sure the
        view is available without any prior auth of handshake.
        """
        view = LoginProviderViewSet
        factory = APIRequestFactory()
        list_view = view.as_view({"get": "list"})
        response = list_view(factory.get(""))
        self.assertEqual(response.status_code, 200)


class TestAppContextView(TestCase):
    def test_anonymous_can_see_view(self):
        """
        This view is required by a front end to know provide
        application configuration data. Since this happens
        prior to user interaction the frontend needs to get
        this data without prior context.
        """
        view = AppContextViewSet
        factory = APIRequestFactory()
        list_view = view.as_view({"get": "list"})
        response = list_view(factory.get(""))
        self.assertEqual(response.status_code, 200)
