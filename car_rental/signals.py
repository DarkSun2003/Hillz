from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import User, UserProfile, Customer, Rental, Purchase, Car, SiteInfo, DiagnosticService, RepairService, UpgradeService, ConsultationService

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a UserProfile when a User is created.
    Uses get_or_create to prevent IntegrityError if triggered multiple times.
    """
    if created: # Only run on initial creation
        try:
            # Use get_or_create to prevent unique constraint violations
            UserProfile.objects.get_or_create(user=instance)
        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating user profile: {e}")

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save the UserProfile when the User is saved.
    Prevents IntegrityError by checking if the profile already exists.
    """
    # FIX: Ensure we do NOT try to create the profile here if it doesn't exist,
    # as create_user_profile handles initial creation. This handler should only save.
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        # Removed the fallback creation: else: UserProfile.objects.create(user=instance)
        # We rely on the 'created' check in create_user_profile for initial setup.
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error saving user profile: {e}")


@receiver(post_save, sender=User)
def create_customer_for_user(sender, instance, created, **kwargs):
    """
    Create a Customer record when a User with email is created
    """
    # FIX: Ensure this also only runs on initial creation (created=True)
    if created and instance.email:
        try:
            # Note: Your Customer model definition allows this to be created separately.
            Customer.objects.get_or_create(
                email=instance.email,
                defaults={'name': f"{instance.first_name} {instance.last_name}".strip() or instance.username,
                'user': instance}# Link User to Customer upon creation
            )
        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating customer for user: {e}")

@receiver(pre_save, sender=Rental)
def update_car_status_on_rental(sender, instance, **kwargs):
    """
    Update car status when rental is created or updated
    Changes 'available' -> 'rented' and 'rented' -> 'available'
    """
    try:
        # Check if car status needs to be updated
        car = instance.car
        if instance.pk:  # Updating existing rental
            old_rental = Rental.objects.get(pk=instance.pk)
            
            # Going Active/Overdue (car becomes 'rented')
            if instance.status in ['active', 'overdue'] and old_rental.status not in ['active', 'overdue'] and car.status == 'available':
                car.status = 'rented'
                car.save()
            
            # Going Completed/Cancelled (car becomes 'available')
            elif instance.status in ['completed', 'cancelled'] and old_rental.status not in ['completed', 'cancelled'] and car.status == 'rented':
                car.status = 'available'
                car.save()
        else:  # Creating new rental
            if instance.status == 'active' and car.status == 'available':
                car.status = 'rented'
                car.save()
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating car status on rental pre_save: {e}")

@receiver(pre_save, sender=Purchase)
def update_car_status_on_purchase(sender, instance, **kwargs):
    """
    Update car status to 'sold' before it's soft-deleted upon delivery.
    """
    try:
        car = instance.car
        if not car:
            return # Skip if no car linked (i.e., after deletion in models.py)
            
        if instance.pk:  # Updating existing purchase
            old_purchase = Purchase.objects.get(pk=instance.pk)
            
            # If status is changing to delivered, ensure car status is marked as sold
            if instance.status == 'delivered' and old_purchase.status != 'delivered' and car.status != 'sold':
                car.status = 'sold'
                car.save()
        else:  # Creating new purchase
            if instance.status == 'delivered' and car.status != 'sold':
                car.status = 'sold'
                car.save()
                
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating car status on purchase pre_save: {e}")

@receiver(post_save, sender=Rental)
def send_rental_notification(sender, instance, created, **kwargs):
    """
    Send notifications when rental is created or status changes
    """
    try:
        site_info = SiteInfo.objects.first()
        if not site_info:
            return
        
        if created:
            # Send confirmation email to customer
            from .utils import send_rental_confirmation_email
            send_rental_confirmation_email(instance)
            
            # Notify staff about new rental
            if site_info.email:
                subject = f"New Rental: {instance.car.make} {instance.car.model}"
                message = f"A new rental has been created for {instance.customer.name} from {instance.rental_datetime} to {instance.return_datetime}."
                
                send_mail(
                    subject,
                    message,
                    site_info.email,
                    [site_info.email],
                    fail_silently=True,
                )
        else:
            # Check if status changed to overdue
            if instance.status == 'overdue':
                # Send overdue notification to customer
                subject = f"Rental Overdue: {instance.car.make} {instance.car.model}"
                
                context = {
                    'rental': instance,
                    'site_info': site_info,
                    'customer_name': instance.customer.name,
                    'car_name': f"{instance.car.year} {instance.car.make} {instance.car.model}",
                    'due_date': instance.return_datetime.strftime('%B %d, %Y'),
                    'days_overdue': (timezone.now().date() - instance.return_datetime.date()).days,
                }
                
                html_message = render_to_string('emails/rental_overdue.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject,
                    plain_message,
                    site_info.email,
                    [instance.customer.email],
                    html_message=html_message,
                    fail_silently=True,
                )
                
                # Notify staff about overdue rental
                staff_subject = f"Overdue Rental: {instance.car.make} {instance.car.model}"
                staff_message = f"The rental for {instance.customer.name} is overdue by {(timezone.now().date() - instance.return_datetime.date()).days} days."
                
                send_mail(
                    staff_subject,
                    staff_message,
                    site_info.email,
                    [site_info.email],
                    fail_silently=True,
                )
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending rental notification: {e}")

@receiver(post_save, sender=Purchase)
def send_purchase_notification(sender, instance, created, **kwargs):
    """
    Send notifications when purchase is created or status changes
    """
    try:
        site_info = SiteInfo.objects.first()
        if not site_info:
            return
        
        if created:
            # Send confirmation email to customer
            from .utils import send_purchase_confirmation_email
            send_purchase_confirmation_email(instance)
            
            # Notify staff about new purchase
            if site_info.email:
                subject = f"New Purchase: {instance.car.make} {instance.car.model}"
                message = f"A new purchase has been made by {instance.customer.name} on {instance.purchase_datetime}."
                
                send_mail(
                    subject,
                    message,
                    site_info.email,
                    [site_info.email],
                    fail_silently=True,
                )
        else:
            # Check if status changed to delivered
            if instance.status == 'delivered':
                # Send delivery confirmation to customer
                subject = f"Purchase Delivered: {instance.car.make} {instance.car.model}"
                
                context = {
                    'purchase': instance,
                    'site_info': site_info,
                    'customer_name': instance.customer.name,
                    'car_name': f"{instance.car.year} {instance.car.make} {instance.car.model}",
                    'delivery_date': instance.actual_delivery_datetime.strftime('%B %d, %Y') if instance.actual_delivery_datetime else 'N/A',
                }
                
                html_message = render_to_string('emails/purchase_delivered.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject,
                    plain_message,
                    site_info.email,
                    [instance.customer.email],
                    html_message=html_message,
                    fail_silently=True,
                )
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending purchase notification: {e}")

@receiver(post_save, sender=DiagnosticService)
def send_diagnostic_service_notification(sender, instance, created, **kwargs):
    """
    Send notifications when diagnostic service is created or status changes
    """
    try:
        site_info = SiteInfo.objects.first()
        if not site_info:
            return
        
        if created:
            # Send confirmation email to customer
            from .utils import send_service_confirmation_email
            send_service_confirmation_email(instance)
            
            # Notify staff about new service
            if site_info.email and instance.technician:
                subject = f"New Diagnostic Service: {instance.title}"
                message = f"A new diagnostic service has been created for {instance.customer.name} scheduled for {instance.scheduled_date}."
                
                send_mail(
                    subject,
                    message,
                    site_info.email,
                    [instance.technician.email],
                    fail_silently=True,
                )
        elif instance.status == 'completed':
            # Send completion notification to customer
            subject = f"Diagnostic Service Completed: {instance.title}"
            
            context = {
                'service': instance,
                'site_info': site_info,
                'customer_name': instance.customer.name,
                'service_title': instance.title,
                'completed_date': instance.completed_date.strftime('%B %d, %Y'),
            }
            
            html_message = render_to_string('emails/service_completed.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                site_info.email,
                [instance.customer.email],
                html_message=html_message,
                fail_silently=True,
            )
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending diagnostic service notification: {e}")

@receiver(post_save, sender=RepairService)
def send_repair_service_notification(sender, instance, created, **kwargs):
    """
    Send notifications when repair service is created or status changes
    """
    try:
        site_info = SiteInfo.objects.first()
        if not site_info:
            return
        
        if created:
            # Send confirmation email to customer
            from .utils import send_service_confirmation_email
            send_service_confirmation_email(instance)
            
            # Notify staff about new service
            if site_info.email and instance.technician:
                subject = f"New Repair Service: {instance.title}"
                message = f"A new repair service has been created for {instance.customer.name} scheduled for {instance.scheduled_date}."
                
                send_mail(
                    subject,
                    message,
                    site_info.email,
                    [instance.technician.email],
                    fail_silently=True,
                )
        elif instance.status == 'completed':
            # Send completion notification to customer
            subject = f"Repair Service Completed: {instance.title}"
            
            context = {
                'service': instance,
                'site_info': site_info,
                'customer_name': instance.customer.name,
                'service_title': instance.title,
                'completed_date': instance.completed_date.strftime('%B %d, %Y'),
                'warranty_expiry': instance.warranty_expiry.strftime('%B %d, %Y') if instance.warranty_expiry else 'N/A',
            }
            
            html_message = render_to_string('emails/service_completed.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                site_info.email,
                [instance.customer.email],
                html_message=html_message,
                fail_silently=True,
            )
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending repair service notification: {e}")

@receiver(post_save, sender=UpgradeService)
def send_upgrade_service_notification(sender, instance, created, **kwargs):
    """
    Send notifications when upgrade service is created or status changes
    """
    try:
        site_info = SiteInfo.objects.first()
        if not site_info:
            return
        
        if created:
            # Send confirmation email to customer
            from .utils import send_service_confirmation_email
            send_service_confirmation_email(instance)
            
            # Notify staff about new service
            if site_info.email and instance.technician:
                subject = f"New Upgrade Service: {instance.title}"
                message = f"A new upgrade service has been created for {instance.customer.name} scheduled for {instance.scheduled_date}."
                
                send_mail(
                    subject,
                    message,
                    site_info.email,
                    [instance.technician.email],
                    fail_silently=True,
                )
        elif instance.status == 'completed':
            # Send completion notification to customer
            subject = f"Upgrade Service Completed: {instance.title}"
            
            context = {
                'service': instance,
                'site_info': site_info,
                'customer_name': instance.customer.name,
                'service_title': instance.title,
                'completed_date': instance.completed_date.strftime('%B %d, %Y'),
                'warranty_expiry': instance.warranty_expiry.strftime('%B %d, %Y') if instance.warranty_expiry else 'N/A',
                'horsepower_increase': instance.horsepower_increase,
                'torque_increase': instance.torque_increase,
            }
            
            html_message = render_to_string('emails/service_completed.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                site_info.email,
                [instance.customer.email],
                html_message=html_message,
                fail_silently=True,
            )
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending upgrade service notification: {e}")

@receiver(post_save, sender=ConsultationService)
def send_consultation_service_notification(sender, instance, created, **kwargs):
    """
    Send notifications when consultation service is created or status changes
    """
    try:
        site_info = SiteInfo.objects.first()
        if not site_info:
            return
        
        if created:
            # Send confirmation email to customer
            from .utils import send_service_confirmation_email
            send_service_confirmation_email(instance)
            
            # Notify staff about new service
            if site_info.email and instance.consultant:
                subject = f"New Consultation Service: {instance.title}"
                message = f"A new consultation service has been created for {instance.customer.name} scheduled for {instance.scheduled_date}."
                
                send_mail(
                    subject,
                    message,
                    site_info.email,
                    [instance.consultant.email],
                    fail_silently=True,
                )
        elif instance.status == 'completed':
            # Send completion notification to customer
            subject = f"Consultation Service Completed: {instance.title}"
            
            context = {
                'service': instance,
                'site_info': site_info,
                'customer_name': instance.customer.name,
                'service_title': instance.title,
                'completed_date': instance.completed_date.strftime('%B %d, %Y'),
            }
            
            html_message = render_to_string('emails/service_completed.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                site_info.email,
                [instance.customer.email],
                html_message=html_message,
                fail_silently=True,
            )
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending consultation service notification: {e}")

@receiver(pre_delete, sender=Car)
def prevent_car_deletion_with_active_rentals(sender, instance, **kwargs):
    """
    Prevent deletion of cars with active rentals
    """
    try:
        active_rentals = instance.rentals.filter(status__in=['active', 'overdue'])
        if active_rentals.exists():
            raise ValueError("Cannot delete car with active rentals")
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error preventing car deletion: {e}")
        raise e