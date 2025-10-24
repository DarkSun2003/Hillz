from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def format_naira_price(value):
    """
    Format a price in Nigerian Naira currency.
    Example: 5000.00 → ₦5,000.00
    """
    try:
        # Convert to Decimal if it's not already
        if value is None:
            return "₦0.00"
        
        # Handle string values
        if isinstance(value, str):
            value = Decimal(value.replace(',', ''))
        
        # Ensure it's a Decimal
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Format with commas and Naira symbol
        return f"₦{value:,.2f}"
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return "₦0.00"

@register.filter
def multiply(value, arg):
    """
    Multiply the value by the argument.
    Example: {{ car.daily_rate|multiply:7 }}
    """
    try:
        if value is None:
            return Decimal('0.00')
        
        # Handle string values
        if isinstance(value, str):
            value = Decimal(value.replace(',', ''))
        
        # Ensure it's a Decimal
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Handle string arguments
        if isinstance(arg, str):
            arg = Decimal(arg.replace(',', ''))
        
        # Ensure arg is a Decimal
        if not isinstance(arg, Decimal):
            arg = Decimal(str(arg))
        
        # Multiply and return
        return value * arg
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return Decimal('0.00')

@register.filter
def subtract(value, arg):
    """
    Subtract the argument from the value.
    Example: {{ car.default_price|subtract:car.sale_price }}
    """
    try:
        if value is None or arg is None:
            return Decimal('0.00')
        
        # Handle string values
        if isinstance(value, str):
            value = Decimal(value.replace(',', ''))
        
        if isinstance(arg, str):
            arg = Decimal(arg.replace(',', ''))
        
        # Ensure they are Decimals
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        if not isinstance(arg, Decimal):
            arg = Decimal(str(arg))
        
        # Subtract and return
        return value - arg
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return Decimal('0.00')

@register.filter
def service_type_color(value):
    """
    Return the appropriate Bootstrap color class for a service type.
    """
    service_type_colors = {
        'diagnostic': 'primary',
        'repair': 'success',
        'upgrade': 'warning',
        'consultation': 'info',
    }
    return service_type_colors.get(value, 'secondary')


@register.filter
def currency(value):
    """
    Format a value as currency with the Naira symbol (₦)
    """
    try:
        value = float(value)
        return f"₦{value:,.2f}"
    except (ValueError, TypeError):
        return "₦0.00"