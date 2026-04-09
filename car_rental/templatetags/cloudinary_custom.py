from django import template
from cloudinary.utils import cloudinary_url

register = template.Library()

@register.simple_tag
def cloudinary_image_url(image, width=None, height=None, crop=None, format=None, quality=None, **kwargs):
    """
    Returns a Cloudinary image URL with automatic optimization
    """
    if not image:
        return ""
    
    options = {}
    if width:
        options['width'] = width
    if height:
        options['height'] = height
    if crop:
        options['crop'] = crop
    if format:
        options['format'] = format
    if quality:
        options['quality'] = quality
    
    # Add automatic optimizations if not specified
    if 'quality' not in options:
        options['quality'] = 'auto:best'
    if 'format' not in options:
        options['format'] = 'auto'
    
    # Add any additional transformations
    options.update(kwargs)
    
    return cloudinary_url(image, **options)

@register.simple_tag
def cloudinary_url_tag(image, **kwargs):
    """
    Returns a Cloudinary URL for transformations (alias for cloudinary_image_url)
    """
    return cloudinary_image_url(image, **kwargs)