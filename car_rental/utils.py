from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db.models import Sum
import math
import os
from .models import Rental, Purchase, SiteInfo, ServiceBooking

def send_rental_confirmation_email(rental):
    """
    Send rental confirmation email to customer
    """
    site_info = SiteInfo.objects.first()
    if not site_info:
        site_info = SiteInfo()
    
    subject = f"Rental Confirmation - {rental.car.make} {rental.car.model}"
    
    context = {
        'rental': rental,
        'site_info': site_info,
        'customer_name': rental.customer.name,
        'car_name': f"{rental.car.year} {rental.car.make} {rental.car.model}",
        'rental_date': rental.rental_datetime.strftime('%B %d, %Y'),
        'return_date': rental.return_datetime.strftime('%B %d, %Y'),
        'daily_rate': rental.daily_rate,
        'total_amount': rental.total_amount,
        'pickup_location': rental.pickup_location or site_info.address,
    }
    
    html_message = render_to_string('emails/rental_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    from_email = site_info.email
    to_email = rental.customer.email
    
    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending rental confirmation email: {e}")
        return False

def send_purchase_confirmation_email(purchase):
    """
    Send purchase confirmation email to customer
    """
    site_info = SiteInfo.objects.first()
    if not site_info:
        site_info = SiteInfo()
    
    subject = f"Purchase Confirmation - {purchase.car.make} {purchase.car.model}"
    
    context = {
        'purchase': purchase,
        'site_info': site_info,
        'customer_name': purchase.customer.name,
        'car_name': f"{purchase.car.year} {purchase.car.make} {purchase.car.model}",
        'purchase_date': purchase.purchase_datetime.strftime('%B %d, %Y'),
        'purchase_price': purchase.purchase_price,
        'total_amount': purchase.total_amount,
    }
    
    html_message = render_to_string('emails/purchase_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    from_email = site_info.email
    to_email = purchase.customer.email
    
    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending purchase confirmation email: {e}")
        return False

def send_service_confirmation_email(booking):
    # New code using ServiceBooking model
    site_info = SiteInfo.objects.first()
    if not site_info:
        site_info = SiteInfo()
    
    subject = f"{booking.get_service_type_display()} Confirmation - {booking.title}"
    
    context = {
        'booking': booking,
        'site_info': site_info,
        'customer_name': booking.name,
        'service_type': booking.get_service_type_display(),
        'scheduled_date': booking.preferred_date,
    }
    
    html_message = render_to_string('emails/service_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    from_email = site_info.email
    to_email = booking.email
    
    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending service confirmation email: {e}")
        return False

def send_password_reset_email(user):
    """
    Send password reset email to user
    """
    site_info = SiteInfo.objects.first()
    if not site_info:
        site_info = SiteInfo()
    
    subject = "Password Reset Request"
    
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    
    context = {
        'user': user,
        'site_info': site_info,
        'reset_url': f"{settings.SITE_URL}/reset-password/{uid}/{token}/",
    }
    
    html_message = render_to_string('emails/password_reset.html', context)
    plain_message = strip_tags(html_message)
    
    from_email = site_info.email
    to_email = user.email
    
    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on Earth using Haversine formula
    Returns distance in kilometers
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of Earth in kilometers
    r = 6371
    
    return c * r

def generate_invoice_number(prefix, model):
    """
    Generate a unique invoice number with the given prefix
    """
    date_str = datetime.now().strftime('%Y%m%d')
    last_invoice = model.objects.filter(invoice_number__startswith=f"{prefix}{date_str}").order_by('-invoice_number').first()
    
    if last_invoice:
        last_number = int(last_invoice.invoice_number[-4:])
        new_number = str(last_number + 1).zfill(4)
    else:
        new_number = '0001'
    
    return f"{prefix}{date_str}{new_number}"

CURRENCY_SYMBOLS = {
    'NGN': '₦',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
}

def format_currency(amount, currency_code='NGN'):
    """
    Format currency amount with proper symbol and formatting based on code.
    Defaults to NGN if code is unrecognized.
    """
    # Ensure amount is a number
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return f"N/A ₦"
    
    symbol = '₦'
    
    return f"{symbol}{amount:,.2f}"

def format_rental_price(amount):
    """
    Format rental price specifically in Nigerian Naira (₦).
    """
    return format_currency(amount, currency_code='NGN')

def get_business_hours():
    """
    Get current business hours based on day of week
    """
    site_info = SiteInfo.objects.first()
    if not site_info:
        return "9:00 AM - 8:00 PM"
    
    today = datetime.now().strftime("%A").lower()
    return getattr(site_info, f"{today}_hours", "Closed")

def is_business_hours():
    """
    Check if current time is within business hours
    """
    site_info = SiteInfo.objects.first()
    if not site_info:
        return True
    
    today = datetime.now().strftime("%A").lower()
    hours_str = getattr(site_info, f"{today}_hours", "Closed")
    
    if hours_str == "Closed":
        return False
    
    try:
        open_time_str, close_time_str = hours_str.split(' - ')
        open_time = datetime.strptime(open_time_str, '%I:%M %p').time()
        close_time = datetime.strptime(close_time_str, '%I:%M %p').time()
        
        now = datetime.now().time()
        return open_time <= now <= close_time
    except:
        return True

def get_upcoming_maintenance():
    """
    Get cars that need maintenance soon
    """
    from .models import Car, RepairService
    
    # Get cars with maintenance due in the next 30 days
    thirty_days_from_now = datetime.now().date() + timedelta(days=30)
    
    cars_with_upcoming_maintenance = []
    
    for car in Car.objects.filter(status='available'):
        last_maintenance = RepairService.objects.filter(car=car).order_by('-completed_date').first()
        
        if last_maintenance and last_maintenance.warranty_expiry:
            if last_maintenance.warranty_expiry <= thirty_days_from_now:
                cars_with_upcoming_maintenance.append({
                    'car': car,
                    'due_date': last_maintenance.warranty_expiry,
                    'days_until_due': (last_maintenance.warranty_expiry - datetime.now().date()).days
                })
    
    return cars_with_upcoming_maintenance

def get_revenue_report(start_date, end_date):
    """
    Generate revenue report for a given date range
    """
    rentals = Rental.objects.filter(
        rental_datetime__date__gte=start_date,
        rental_datetime__date__lte=end_date,
        payment_status='paid'
    )
    
    purchases = Purchase.objects.filter(
        purchase_datetime__date__gte=start_date,
        purchase_datetime__date__lte=end_date,
        payment_status='paid'
    )
    
    rental_revenue = rentals.aggregate(total=Sum('total_amount'))['total'] or 0
    purchase_revenue = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
    total_revenue = rental_revenue + purchase_revenue
    
    return {
        'rental_revenue': rental_revenue,
        'purchase_revenue': purchase_revenue,
        'total_revenue': total_revenue,
        'rental_count': rentals.count(),
        'purchase_count': purchases.count(),
    }

def handle_uploaded_file(f, upload_dir):
    """
    Handle file upload and save to specified directory
    """
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    filename = f.name
    filepath = os.path.join(upload_dir, filename)
    
    with open(filepath, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    
    return filepath
