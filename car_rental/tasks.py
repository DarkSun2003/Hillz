from django.utils import timezone
from datetime import timedelta
from .models import Rental, Purchase

def update_rental_statuses():
    today = timezone.now().date()
    
    # Update overdue rentals
    overdue_rentals = Rental.objects.filter(
        status='active',
        return_date__lt=today
    )
    overdue_rentals.update(status='overdue')
    
    return f"Updated {overdue_rentals.count()} rentals to overdue status"

def update_purchase_statuses():
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=7)
    
    # Cancel old pending purchases
    old_pending_purchases = Purchase.objects.filter(
        status='pending',
        purchase_date__lt=seven_days_ago
    )
    old_pending_purchases.update(status='cancelled')
    
    return f"Cancelled {old_pending_purchases.count()} old pending purchases"
