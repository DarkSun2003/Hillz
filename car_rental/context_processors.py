from .models import SiteInfo
from django.conf import settings

def get_site_info_context(request):
    """
    Add site_info to all templates
    """
    return {'site_info': SiteInfo.objects.first()}


def marketing_keys(request):
    """
    Makes marketing API keys globally available to all templates.
    """
    return {
        'GOOGLE_ANALYTICS_ID': getattr(settings, 'GOOGLE_ANALYTICS_ID', ''),
        'META_PIXEL_ID': getattr(settings, 'META_PIXEL_ID', ''),
    }