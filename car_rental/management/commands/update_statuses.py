# car_rental/management/commands/update_statuses.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from car_rental.models import Rental, Purchase

class Command(BaseCommand):
    help = 'Updates rental and purchase statuses based on dates and conditions'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Update rental statuses
        self.stdout.write("Checking rental statuses...")
        
        # Find active rentals that are overdue (return date has passed)
        overdue_rentals = Rental.objects.filter(
            status='active',
            return_date__lt=today
        )
        
        overdue_count = overdue_rentals.count()
        if overdue_count > 0:
            overdue_rentals.update(status='overdue')
            self.stdout.write(
                self.style.SUCCESS(f'Updated {overdue_count} rental(s) to overdue status.')
            )
        else:
            self.stdout.write(self.style.WARNING('No overdue rentals found.'))
        
        # Update purchase statuses
        self.stdout.write("Checking purchase statuses...")
        
        # Find pending purchases that are older than 7 days
        seven_days_ago = today - timedelta(days=7)
        old_pending_purchases = Purchase.objects.filter(
            status='pending',
            purchase_date__lt=seven_days_ago
        )
        
        pending_count = old_pending_purchases.count()
        if pending_count > 0:
            old_pending_purchases.update(status='cancelled')
            self.stdout.write(
                self.style.SUCCESS(f'Updated {pending_count} purchase(s) to cancelled status.')
            )
        else:
            self.stdout.write(self.style.WARNING('No old pending purchases found.'))
        
        self.stdout.write(self.style.SUCCESS('Status update completed.'))