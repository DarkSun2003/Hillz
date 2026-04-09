from .models import SiteInfo

def get_site_info_context(request):
    """
    Add site_info to all templates
    """
    return {'site_info': SiteInfo.objects.first()}