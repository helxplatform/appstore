from django.apps import AppConfig
from django.conf import settings


class AppsCoreServicesConfig(AppConfig):
    name = 'core'

    def ready(self):
        import core.signals
        self._pin_saml_sp_entity_id()

    @staticmethod
    def _pin_saml_sp_entity_id():
        if getattr(settings, "ALLOW_SAML_LOGIN", "").lower() != "true":
            return
        sp_entity_id = getattr(settings, "SAML_SP_ENTITY_ID", None)
        sp_acs_url = getattr(settings, "SAML_SP_ACS_URL", None)
        if not sp_entity_id and not sp_acs_url:
            return
        from allauth.socialaccount.providers.saml import utils as saml_utils
        original_build = saml_utils.build_sp_config

        def build_sp_config_pinned(request, provider_config, org):
            config = original_build(request, provider_config, org)
            if sp_entity_id:
                config["entityId"] = sp_entity_id
            if sp_acs_url:
                config["assertionConsumerService"]["url"] = sp_acs_url
            return config

        saml_utils.build_sp_config = build_sp_config_pinned

        # Ambassador overwrites X-Forwarded-Proto based on its own listener
        # scheme (http), so Django's request.is_secure() always returns False.
        # Force the scheme to match the SP entity ID.
        if sp_entity_id and sp_entity_id.startswith("https://"):
            original_prepare = saml_utils.prepare_django_request

            def prepare_django_request_pinned(request):
                result = original_prepare(request)
                result["https"] = "on"
                return result

            saml_utils.prepare_django_request = prepare_django_request_pinned