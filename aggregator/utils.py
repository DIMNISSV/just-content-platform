def check_provider_auth(request):
    from aggregator.models import PluginProvider
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    return PluginProvider.objects.filter(api_token=token, is_active=True).first()
