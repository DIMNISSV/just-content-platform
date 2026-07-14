from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def taxonomy_manager_view(request):
    """
    Renders the custom Vue-based Taxonomy Manager page in Django Admin.
    """
    context = {
        'site_header': 'Just Content Admin',
        'has_permission': True,
        'is_popup': False,
    }
    return render(request, 'admin/taxonomy_manager.html', context)
