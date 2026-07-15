from django.db.models import Lookup


class PostgresILIKEIContains(Lookup):
    lookup_name = 'icontains'

    def as_postgresql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"{lhs} ILIKE {rhs}", params


class PostgresILIKEIStartsWith(Lookup):
    lookup_name = 'istartswith'

    def as_postgresql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"{lhs} ILIKE {rhs}", params


class PostgresILIKEIEndsWith(Lookup):
    lookup_name = 'iendswith'

    def as_postgresql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"{lhs} ILIKE {rhs}", params


class PostgresILIKEIExact(Lookup):
    lookup_name = 'iexact'

    def as_postgresql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"{lhs} ILIKE {rhs}", params
