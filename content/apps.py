from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = 'content'

    def ready(self):
        # Implicitly connect signal handlers when the app is ready
        import content.signals
