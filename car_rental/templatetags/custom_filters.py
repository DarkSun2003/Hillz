from django import template

register = template.Library()

@register.filter
def class_name(value, class_str):
    return value.__class__.__name__ == class_str


@register.filter
def subtract(value, arg):
    """Subtracts the arg from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def add(value, arg):
    """Adds the arg to the value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0
    
    
from django.db.models import Sum

@register.filter
def filter_status(purchases, status):
    """Filter purchases by status"""
    return [p for p in purchases if p.status == status]

@register.filter
def total_revenue(purchases):
    """Calculate total revenue from purchases"""
    return sum(purchase.total_amount for purchase in purchases if purchase.total_amount)


@register.filter
def format_naira_price(value):
    """
    Format a number as Nigerian Naira currency
    """
    if value is None:
        return "₦0.00"
    try:
        value = float(value)
        return f"₦{value:,.2f}"
    except (ValueError, TypeError):
        return "₦0.00"
    
@register.filter
def add_class(value, arg):
    """
    Add a CSS class to a form field
    """
    if value:
        return f'{value} {arg}'
    return value


@register.filter
def remove_non_numeric(value):
    """Remove all non-numeric characters from a string."""
    if value is None:
        return ""
    return ''.join(filter(str.isdigit, str(value)))

@register.filter
def service_type_color(service_type):
    """Return a color based on service type"""
    colors = {
        'diagnostic': 'info',
        'repair': 'warning',
        'upgrade': 'primary',
        'consultation': 'success'
    }
    return colors.get(service_type, 'secondary')