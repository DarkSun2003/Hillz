from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from car_rental.models import Customer

User = get_user_model()

class Command(BaseCommand):
    help = 'Create customer accounts for users without them'

    def handle(self, *args, **options):
        users_without_customers = User.objects.filter(customer_account__isnull=True, email__isnull=False)
        
        for user in users_without_customers:
            customer, created = Customer.objects.get_or_create(
                email=user.email,
                defaults={
                    'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'user': user
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created customer account for user: {user.username}')
                )
            else:
                # If customer already exists but not linked, link it
                user.customer_account = customer
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Linked existing customer account to user: {user.username}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed {users_without_customers.count()} users')
        )