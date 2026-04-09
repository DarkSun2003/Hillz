from django.core.management.base import BaseCommand
from django_q.models import Schedule
from django.utils import timezone
from datetime import time

class Command(BaseCommand):
    help = 'Schedules daily status update tasks'

    def handle(self, *args, **options):
        # Schedule rental status update to run daily at 1 AM
        Schedule.objects.create(
            func='car_rental.tasks.update_rental_statuses',
            schedule_type=Schedule.DAILY,
            next_run=timezone.now().replace(hour=1, minute=0, second=0, microsecond=0)
        )
        
        # Schedule purchase status update to run daily at 1:05 AM
        Schedule.objects.create(
            func='car_rental.tasks.update_purchase_statuses',
            schedule_type=Schedule.DAILY,
            next_run=timezone.now().replace(hour=1, minute=5, second=0, microsecond=0)
        )
        
        self.stdout.write(self.style.SUCCESS('Successfully scheduled daily status update tasks.'))