from django.apps import AppConfig


class AppsCoreServicesConfig(AppConfig):
    name = 'core'

    def ready(self):
        import core.signals