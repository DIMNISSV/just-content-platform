from django.db.models import Q


def parse_ast_to_q(node: dict) -> Q:
    if not node or not isinstance(node, dict):
        return Q()

    node_type = node.get('type')

    if node_type == 'RULE':
        field = node.get('field')
        operator = node.get('operator', 'exact')
        value = node.get('value')

        if not field or value is None or value == '':
            return Q()

        field_mapping = {
            'genre': 'genres__slug',
            'type': 'type',
            'release_year': 'release_year',
            'rating_score': 'rating_score',
            'votes_count': 'votes_count',
            'name': 'name__icontains',
        }

        orm_field = field_mapping.get(field)
        if not orm_field:
            return Q()

        if operator != 'exact' and field != 'name':
            lookup = f"{orm_field}__{operator}"
        else:
            lookup = orm_field

        return Q(**{lookup: value})

    elif node_type == 'AND':
        q = Q()
        for child in node.get('children', []):
            q &= parse_ast_to_q(child)
        return q

    elif node_type == 'OR':
        q = Q()
        children = node.get('children', [])
        if not children:
            return q

        first = True
        for child in children:
            if first:
                q = parse_ast_to_q(child)
                first = False
            else:
                q |= parse_ast_to_q(child)
        return q

    elif node_type == 'NOT':
        q = Q()
        for child in node.get('children', []):
            q &= parse_ast_to_q(child)
        return ~q

    return Q()
