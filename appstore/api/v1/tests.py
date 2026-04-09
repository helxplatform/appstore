import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework.test import APIRequestFactory, force_authenticate

from kube.models import InstanceStatus

from .views import (
    AppViewSet,
    InstanceViewSet,
    UsersViewSet,
    LoginProviderViewSet,
    AppContextViewSet,
)


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


class TestInstanceView(TestCase):
    def setUp(self):
        self.username = "instance_api_tester"
        self.password = "h82VBBBRM&c2aH59a*a!"
        self.user = User.objects.create_superuser(
            self.username, "instance-test@renci-example.com", self.password
        )

        self.factory = APIRequestFactory()
        self.view = InstanceViewSet

    def test_anonymous_cannot_see_view(self):
        list_view = self.view.as_view({"get": "list"})
        response = list_view(self.factory.get(""))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_can_get_instance_list(self):
        user = User.objects.get(username=self.username)
        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("")
        force_authenticate(api_request, user=user)
        response = list_view(api_request)
        self.assertEqual(response.status_code, 200)

    @patch("appstore.api.v1.views.get_registry")
    @patch("appstore.api.v1.views._get_status_query")
    def test_logged_in_can_get_instance_list_with_aggregated_memory(
        self, mock_get_status_query, mock_get_registry
    ):
        user = User.objects.get(username=self.username)
        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("", HTTP_HOST="example.test")
        force_authenticate(api_request, user=user)

        mock_status_query = Mock()
        mock_status_query.by_username.return_value = [
            InstanceStatus(
                name="jupyter-abc123",
                instance_id="abc123",
                app_name="jupyter",
                username=user.username.lower(),
                creation_time="2026-04-04T19:36:54Z",
                is_ready=True,
                resource_usage={
                    "notebook": {
                        "cpu": "1",
                        "memory": "2Gi",
                        "nvidia.com/gpu": "0",
                    }
                },
            )
        ]
        mock_get_status_query.return_value = mock_status_query

        mock_registry = Mock()
        mock_registry.get_app.return_value = SimpleNamespace(
            name="JupyterLab",
            docs_url="https://docs.example.test/jupyter",
        )
        mock_get_registry.return_value = mock_registry

        response = list_view(api_request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["sid"], "abc123")
        self.assertEqual(
            response.data[0]["url"],
            f"http://example.test/private/jupyter/{user.username}/abc123/",
        )
        self.assertTrue(response.data[0]["memory"])

    @patch("appstore.api.v1.views.get_registry")
    @patch("appstore.api.v1.views._get_status_query")
    def test_is_ready_handles_millicpu_resource_usage(
        self, mock_get_status_query, mock_get_registry
    ):
        user = User.objects.get(username=self.username)
        sid = "72cfc14b174c42eba8b6ee9baddb18ac"
        ready_view = self.view.as_view({"get": "is_ready"})
        api_request = self.factory.get("", HTTP_HOST="example.test")
        force_authenticate(api_request, user=user)

        mock_status_query = Mock()
        mock_status_query.by_username.return_value = [
            InstanceStatus(
                name=f"jupyter-{sid}",
                instance_id=sid,
                app_name="jupyter",
                username=user.username.lower(),
                creation_time="2026-04-09T03:20:47Z",
                is_ready=True,
                resource_usage={
                    "notebook": {
                        "cpu": "2500m",
                        "memory": "4Gi",
                    }
                },
            )
        ]
        mock_get_status_query.return_value = mock_status_query

        mock_registry = Mock()
        mock_registry.get_app.return_value = SimpleNamespace(
            name="JupyterLab",
            docs_url="https://docs.example.test/jupyter",
        )
        mock_get_registry.return_value = mock_registry

        response = ready_view(api_request, sid=sid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"is_ready": True})

    @patch("appstore.api.v1.views.uuid.uuid4")
    @patch("appstore.api.v1.views.UserIdentityToken.objects.create")
    @patch("appstore.api.v1.views._get_helxinst_mgr")
    @patch("appstore.api.v1.views._get_helxapp_mgr")
    @patch("appstore.api.v1.views._get_helxuser_mgr")
    @patch("appstore.api.v1.views.validate_request_resources")
    @patch("appstore.api.v1.views.extract_app_resources")
    @patch("appstore.api.v1.views.get_registry")
    def test_create_sets_nb_prefix_with_instance_guid(
        self,
        mock_get_registry,
        mock_extract_app_resources,
        mock_validate_request_resources,
        mock_get_helxuser_mgr,
        mock_get_helxapp_mgr,
        mock_get_helxinst_mgr,
        mock_create_identity_token,
        mock_uuid4,
    ):
        user = User.objects.get(username=self.username)
        create_view = self.view.as_view({"post": "create"})
        api_request = self.factory.post(
            "",
            {"app_id": "jupyter", "cpus": 1, "gpus": 0, "memory": "2Gi"},
            format="json",
            HTTP_HOST="example.test",
        )
        force_authenticate(api_request, user=user)

        instance_id = "e9cb47849da640a4b0f1b938094ff17d"
        mock_uuid4.return_value = SimpleNamespace(hex=instance_id)

        identity_token = Mock()
        identity_token.token = "token-123"
        identity_token.compute_app_consumer_id.return_value = f"app-{instance_id}"
        mock_create_identity_token.return_value = identity_token

        mock_extract_app_resources.return_value = (None, None)
        mock_validate_request_resources.return_value = None

        mock_registry = Mock()
        mock_registry.build_helxapp.return_value = Mock()
        mock_registry.build_helxinst.return_value = Mock()
        mock_registry.get_app.return_value = SimpleNamespace(name="JupyterLab")
        mock_get_registry.return_value = mock_registry

        response = create_view(api_request)

        self.assertEqual(response.status_code, 200)
        mock_registry.build_helxinst.assert_called_once()
        self.assertEqual(
            mock_registry.build_helxinst.call_args.kwargs["reference_id"],
            instance_id,
        )
        environment = mock_registry.build_helxinst.call_args.kwargs["environment"]
        self.assertEqual(
            environment["NB_PREFIX"],
            f"/private/jupyter/{user.username.lower()}/{instance_id}/",
        )
        self.assertEqual(environment["FB_BASEURL"], environment["NB_PREFIX"])
        self.assertEqual(environment["REFERENCE_ID"], instance_id)
        self.assertEqual(environment["GUID"], instance_id)

    @patch("appstore.api.v1.views._get_helxinst_mgr")
    @patch("appstore.api.v1.views.get_registry")
    @patch("appstore.api.v1.views._get_status_query")
    def test_is_ready_resolves_via_helxinst_controller_uuid(
        self, mock_get_status_query, mock_get_registry, mock_get_helxinst_mgr
    ):
        user = User.objects.get(username=self.username)
        sid = "69c34967103647e19f0ddfe7abbf8f3a"
        controller_uuid = "b08804f0-f46e-4bac-b96f-1a10c1545251"

        mock_status_query = Mock()
        mock_status_query.by_username.return_value = []
        mock_status_query.by_controller_id.return_value = [
            InstanceStatus(
                name=f"pgadmin-{controller_uuid}",
                instance_id=controller_uuid,
                app_name="pgadmin",
                username=user.username.lower(),
                creation_time="2026-04-06T00:06:57Z",
                is_ready=True,
                resource_usage={},
            )
        ]
        mock_get_status_query.return_value = mock_status_query

        mock_registry = Mock()
        mock_registry.get_app.return_value = SimpleNamespace(
            name="pgAdmin",
            docs_url="https://docs.example.test/pgadmin",
        )
        mock_get_registry.return_value = mock_registry

        mock_get_helxinst_mgr.return_value.list.return_value = [
            {
                "metadata": {"name": f"pgadmin-{sid}"},
                "spec": {
                    "userName": user.username.lower(),
                    "referenceID": sid,
                    "environment": {"GUID": sid},
                },
                "status": {"uuid": controller_uuid},
            }
        ]

        ready_view = self.view.as_view({"get": "is_ready"})
        api_request = self.factory.get("", HTTP_HOST="example.test")
        force_authenticate(api_request, user=user)
        response = ready_view(api_request, sid=sid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"is_ready": True})

    @patch("appstore.api.v1.views._get_helxinst_mgr")
    @patch("appstore.api.v1.views.get_registry")
    @patch("appstore.api.v1.views._get_status_query")
    def test_list_normalizes_controller_uuid_to_guid_and_lowercase_url(
        self, mock_get_status_query, mock_get_registry, mock_get_helxinst_mgr
    ):
        user = User.objects.get(username=self.username)
        sid = "69c34967103647e19f0ddfe7abbf8f3a"
        controller_uuid = "3ccf4b07-ea15-488e-9208-48b0e3ffbb53"

        mock_status_query = Mock()
        mock_status_query.by_username.return_value = [
            InstanceStatus(
                name=f"pgadmin-{controller_uuid}-deploy",
                instance_id=controller_uuid,
                controller_id=controller_uuid,
                app_name="pgadmin",
                username=user.username.lower(),
                creation_time="2026-04-06T01:33:16Z",
                is_ready=True,
                resource_usage={},
            )
        ]
        mock_get_status_query.return_value = mock_status_query

        mock_registry = Mock()
        mock_registry.get_app.return_value = SimpleNamespace(
            name="pgAdmin",
            docs_url="https://docs.example.test/pgadmin",
        )
        mock_get_registry.return_value = mock_registry

        mock_get_helxinst_mgr.return_value.list.return_value = [
            {
                "metadata": {"name": f"pgadmin-{sid}"},
                "spec": {
                    "userName": user.username.lower(),
                    "referenceID": sid,
                    "environment": {"GUID": sid},
                },
                "status": {"uuid": controller_uuid},
            }
        ]

        list_view = self.view.as_view({"get": "list"})
        api_request = self.factory.get("", HTTP_HOST="example.test")
        force_authenticate(api_request, user=user)
        response = list_view(api_request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["sid"], sid)
        self.assertEqual(
            response.data[0]["url"],
            f"http://example.test/private/pgadmin/{user.username.lower()}/{sid}/",
        )

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
        self.assertEqual(response.data["ACCESS_TOKEN"], None)

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
        self.assertEqual(
            response.data["ACCESS_TOKEN"], "t6GEUD-DkGzfY-ZGseAu-wPvpFD-989QGj"
        )

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
