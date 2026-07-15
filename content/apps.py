from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = 'content'

    def ready(self):
        import content.signals

        from django.db.models.fields import Field
        from content.lookups import (
            PostgresILIKEIContains,
            PostgresILIKEIStartsWith,
            PostgresILIKEIEndsWith,
            PostgresILIKEIExact
        )
        Field.register_lookup(PostgresILIKEIContains)
        Field.register_lookup(PostgresILIKEIStartsWith)
        Field.register_lookup(PostgresILIKEIEndsWith)
        Field.register_lookup(PostgresILIKEIExact)
