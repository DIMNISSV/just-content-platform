class TenantDomainMiddleware:
    """
    Middleware that extracts the domain from the request host
    and attaches it to the request object.
    This allows downstream views and serializers to filter content based on the domain.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract host without the port number
        host = request.get_host().split(':')[0]
        request.tenant_domain = host

        response = self.get_response(request)
        return response
