from django.apps import AppConfig

class MediaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'media'

    def ready(self):
        # Implicitly connect signal handlers when the app is ready
        import media.signals