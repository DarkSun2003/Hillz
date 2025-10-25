from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.core.validators import RegexValidator
import re
import math
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from cloudinary.models import CloudinaryField

# Abstract Base Models
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class AuditableModel(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='created_%(class)s')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='updated_%(class)s')
    
    class Meta:
        abstract = True

class SoftDeletionModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    
    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()
    
    class Meta:
        abstract = True

class SiteInfo(TimeStampedModel, AuditableModel):
    company_name = models.CharField(max_length=100, default="Hillz Exquisites")
    tagline = models.CharField(max_length=200, default="Premium Car Rentals & Automotive Services")
    description = models.TextField(default="Experience luxury and performance with our exclusive fleet of premium vehicles. Rent, buy, or service your car with confidence at Hillz Exquisites.")
    address = models.TextField(default="123 Luxury Avenue, Beverly Hills, CA 90210")
    phone = models.CharField(max_length=20, default="+1 (234) 567-890")
    whatsapp_phone = models.CharField(max_length=20, blank=True, default="+1 (234) 567-890")
    email = models.EmailField(default="info@hillzexquisites.com")
    
    # Structured business hours
    monday_hours = models.CharField(max_length=50, default="9:00 AM - 8:00 PM")
    tuesday_hours = models.CharField(max_length=50, default="9:00 AM - 8:00 PM")
    wednesday_hours = models.CharField(max_length=50, default="9:00 AM - 8:00 PM")
    thursday_hours = models.CharField(max_length=50, default="9:00 AM - 8:00 PM")
    friday_hours = models.CharField(max_length=50, default="9:00 AM - 8:00 PM")
    saturday_hours = models.CharField(max_length=50, default="10:00 AM - 6:00 PM")
    sunday_hours = models.CharField(max_length=50, default="10:00 AM - 6:00 PM")
    
    # Social Media
    instagram_url = models.URLField(blank=True, default="https://instagram.com")
    
    # Media
    logo = CloudinaryField('logo', folder='site/')
    favicon = CloudinaryField('favicon', folder='site/')
    
    def __str__(self):
        return self.company_name
    
    @property
    def formatted_working_hours(self):
        """Return formatted working hours"""
        days = [
            ("Monday", self.monday_hours),
            ("Tuesday", self.tuesday_hours),
            ("Wednesday", self.wednesday_hours),
            ("Thursday", self.thursday_hours),
            ("Friday", self.friday_hours),
            ("Saturday", self.saturday_hours),
            ("Sunday", self.sunday_hours),
        ]
        return "\n".join([f"{day}: {hours}" for day, hours in days])
    
    def get_current_hours(self):
        """Get today's working hours"""
        today = timezone.now().strftime("%A").lower()
        return getattr(self, f"{today}_hours", "Closed")
    
    def save(self, *args, **kwargs):
        # Ensure only one instance of SiteInfo exists
        if SiteInfo.objects.exists() and not self.pk:
            # If there's already an instance and this is a new one, update the existing one
            existing_info = SiteInfo.objects.first()
            self.pk = existing_info.pk
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Site Information"
        verbose_name_plural = "Site Information"

# Customer Model
class Customer(TimeStampedModel, AuditableModel, SoftDeletionModel):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )]
    )
    address = models.TextField(blank=True)
    delivery_address = models.TextField(blank=True)
    
    is_banned = models.BooleanField(default=False, help_text="Whether this customer is banned from renting or purchasing")
    
    # Driver's license information
    drivers_license = models.CharField(max_length=50, blank=True)
    license_expiry = models.DateField(blank=True, null=True)
    license_image = CloudinaryField('license_image', folder='licenses/')
    
    # User account relationship
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='customer_account'
    )
    
    # Payment methods (encrypted)
    payment_methods = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return self.name
    
    def __str__(self):
        status = " (BANNED)" if self.is_banned else ""
        return f"{self.name}{status}"
    
    def ban(self):
        """Ban this customer"""
        self.is_banned = True
        self.save()
    
    def unban(self):
        """Unban this customer"""
        self.is_banned = False
        self.save()
    
    def clean(self):
        # Validate phone number
        if self.phone and not re.match(r'^\+?1?\d{9,15}$', self.phone.replace(' ', '').replace('-', '')):
            raise ValidationError("Please enter a valid phone number.")
        
        # Validate license expiry
        if self.license_expiry and self.license_expiry < timezone.now().date():
            raise ValidationError("Driver's license has expired.")
    
    def has_valid_license(self):
        """Check if customer has a valid driver's license"""
        if not self.drivers_license or not self.license_expiry:
            return False
        return self.license_expiry > timezone.now().date()
    
    def get_active_rentals(self):
        """Get all active rentals for this customer"""
        return self.rentals.filter(status__in=['active', 'overdue'])
    
    def get_active_purchases(self):
        """Get all pending/processing purchases for this customer"""
        return self.purchases.filter(status__in=['pending', 'processing'])
    
    class Meta:
        ordering = ['name']
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

# Car Model
class Car(TimeStampedModel, AuditableModel, SoftDeletionModel):
    CAR_TYPES = [
        ('sedan', 'Sedan'),
        ('suv', 'SUV'),
        ('coupe', 'Coupe'),
        ('convertible', 'Convertible'),
        ('hatchback', 'Hatchback'),
        ('truck', 'Truck'),
        ('van', 'Van'),
        ('luxury', 'Luxury'),
    ]
    
    TRANSMISSION_TYPES = [
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('cvt', 'CVT'),
        ('semi-automatic', 'Semi-Automatic'),
    ]
    
    ENGINE_TYPES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
        ('plug-in_hybrid', 'Plug-in Hybrid'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('rented', 'Rented'),
        ('in_service', 'In Service'),
        ('sold', 'Sold'),
    ]
    
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.IntegerField()
    default_price = models.DecimalField(
        max_digits=50, 
        decimal_places=2, 
        help_text="Default price used if rent/sale prices not set"
    )
    description = models.TextField()
    image = CloudinaryField('image', folder='cars/')
    featured = models.BooleanField(default=False)
    
    # Vehicle Identification Number
    vin = models.CharField(max_length=17, unique=True, blank=True, null=True, 
                          help_text="Vehicle Identification Number")
    
    # Fuel efficiency
    fuel_efficiency = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        blank=True, 
        null=True,
        help_text="MPG or kWh/100km for electric vehicles"
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    
    # Pricing
    for_rent = models.BooleanField(default=False)
    for_sale = models.BooleanField(default=False)
    rent_price = models.DecimalField(
        max_digits=25, 
        decimal_places=2, 
        blank=True, 
        null=True, 
        help_text="Price per day"
    )
    sale_price = models.DecimalField(max_digits=50, decimal_places=2, blank=True, null=True)
    
    # Specifications
    car_type = models.CharField(max_length=50, choices=CAR_TYPES, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    mileage = models.IntegerField(default=0, help_text="Mileage in miles")
    transmission = models.CharField(max_length=50, choices=TRANSMISSION_TYPES, blank=True, null=True)
    engine_type = models.CharField(max_length=50, choices=ENGINE_TYPES, blank=True, null=True)
    seats = models.IntegerField(default=4)
    
    # Slug for URL
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    
    def __str__(self):
        return f"{self.year} {self.make} {self.model}"
    
    @property
    def get_rent_price(self):
        """Return the rental price of the car"""
        if self.for_rent and self.rent_price:
            return self.rent_price
        return self.default_price
    
    @property
    def get_sale_price(self):
        price = self.sale_price if self.sale_price is not None else self.default_price
        return round(price, 2)
    
    def get_default_image(self):
        """Return a default image if none is provided"""
        if self.image:
            return self.image.url
        return '/static/images/default-car.jpg'
    
    def is_available(self, start_date, end_date):
        """Check if car is available for the given date range"""
        if self.status != 'available':
            return False
            
        # Check if car has any overlapping rentals that are active or overdue (excluding pending)
        overlapping_rentals = self.rentals.filter(
            status__in=['active', 'overdue'],
            return_datetime__gte=start_date,
            rental_datetime__lte=end_date
        )
        return not overlapping_rentals.exists()
    
    def get_current_rental(self):
        """Get the current active rental if any"""
        return self.rentals.filter(status__in=['active', 'overdue']).first()
    
    def clean(self):
        # Validate that at least one of for_rent or for_sale is True
        if not self.for_rent and not self.for_sale:
            raise ValidationError("At least one of 'For Rent' or 'For Sale' must be selected.")
        
        # Validate rent_price if for_rent is True
        if self.for_rent and (self.rent_price is None or self.rent_price <= 0):
            raise ValidationError("Rent price must be specified and greater than zero when 'For Rent' is selected.")
        
        # Validate sale_price if for_sale is True
        if self.for_sale and (self.sale_price is None or self.sale_price <= 0):
            raise ValidationError("Sale price must be specified and greater than zero when 'For Sale' is selected.")
        
        # Validate year is reasonable
        current_year = timezone.now().year
        if self.year < 1900 or self.year > current_year + 1:
            raise ValidationError(f"Year must be between 1900 and {current_year + 1}.")
        
        # Validate VIN format if provided
        if self.vin and not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', self.vin):
            raise ValidationError("Invalid VIN format.")
    
    def save(self, *args, **kwargs):
        # Generate slug if not provided
        if not self.slug:
            self.slug = slugify(f"{self.make}-{self.model}-{self.year}")
            # Ensure slug is unique
            original_slug = self.slug
            counter = 1
            while Car.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-year', 'make', 'model']
        verbose_name = "Car"
        verbose_name_plural = "Cars"

# Rental Model
class Rental(TimeStampedModel, AuditableModel, SoftDeletionModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]
    
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='rentals'
    )
    car = models.ForeignKey(
        Car, 
        on_delete=models.CASCADE, 
        related_name='rentals'
    )
    
    # Use DateTimeField for precise time tracking
    rental_datetime = models.DateTimeField(default=timezone.now)
    return_datetime = models.DateTimeField()
    actual_return_datetime = models.DateTimeField(blank=True, null=True)
    
    # Locations
    pickup_location = models.CharField(max_length=200, blank=True)
    
    # Pricing
    daily_rate = models.DecimalField(max_digits=30, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=50, decimal_places=2, blank=True, null=True)
    late_fee = models.DecimalField(max_digits=50, decimal_places=2, default=0)
    
    # Payment
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    
    # Employee who handled the rental
    employee = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handled_rentals'
    )
    
    # Insurance information
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_policy = models.CharField(max_length=50, blank=True)
    
    #late fee override
    override_late_fee = models.BooleanField(default=False, help_text="Check to manually set late fee instead of calculating automatically")
    manual_late_fee = models.DecimalField(max_digits=50, decimal_places=2, default=0, help_text="Manually set late fee amount")
    
    def clean(self):
        # Validate that return_datetime is after rental_datetime
        if self.return_datetime and self.rental_datetime and self.return_datetime < self.rental_datetime:
            raise ValidationError("Return date must be after rental date.")
        
        # Validate that actual_return_datetime is after rental_datetime
        if self.actual_return_datetime and self.rental_datetime and self.actual_return_datetime < self.rental_datetime:
            raise ValidationError("Actual return date must be after rental date.")
    
    def save(self, *args, **kwargs):
        # Calculate total_amount if not provided
        if not self.total_amount and self.daily_rate and self.return_datetime and self.rental_datetime:
            rental_days = (self.return_datetime.date() - self.rental_datetime.date()).days
            if rental_days < 1:  # Minimum 1 day
                rental_days = 1
            self.total_amount = self.daily_rate * rental_days
        
        # Calculate late fee if applicable and not overridden
        if not self.override_late_fee:
            if self.actual_return_datetime and self.actual_return_datetime > self.return_datetime:
                hours_late = (self.actual_return_datetime - self.return_datetime).total_seconds() / 3600
                # Example: ₦1000 per hour or fraction thereof
                self.late_fee = math.ceil(hours_late) * 1000
            else:
                self.late_fee = 0
        else:
            # Use the manually set late fee
            self.late_fee = self.manual_late_fee
        
        # Auto-update status based on dates
        now = timezone.now()
        if self.status == 'active' and self.return_datetime and self.return_datetime < now:
            self.status = 'overdue'
        elif self.status in ['active', 'overdue'] and self.actual_return_datetime:
            self.status = 'completed'
        
        super().save(*args, **kwargs)

    @property
    def rental_days(self):
        """Calculate the number of rental days."""
        if self.actual_return_datetime:
            end = self.actual_return_datetime.date()
        else:
            end = self.return_datetime.date()
        start = self.rental_datetime.date()
        return (end - start).days

    @property
    def total_amount_due(self):
        """Calculate total amount due including late fees."""
        return (self.total_amount or 0) + self.late_fee
    
    def get_insurance_details(self):
        """Get insurance information for this rental"""
        return {
            'provider': self.insurance_provider,
            'policy': self.insurance_policy,
        }
    
    class Meta:
        ordering = ['-rental_datetime']
        verbose_name = "Rental"
        verbose_name_plural = "Rentals"

# Purchase Model
class Purchase(TimeStampedModel, AuditableModel, SoftDeletionModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='purchases'
    )
    car = models.ForeignKey(
        Car, 
        on_delete=models.CASCADE, 
        related_name='purchases',
        null=True, # Allow null after deletion
        blank=True
    )
    
    # Use DateTimeField for precise time tracking
    purchase_datetime = models.DateTimeField(default=timezone.now)
    delivery_datetime = models.DateTimeField(blank=True, null=True)
    actual_delivery_datetime = models.DateTimeField(blank=True, null=True)
    
    # Pricing - ensure proper decimal places
    purchase_price = models.DecimalField(max_digits=50, decimal_places=2)
    taxes = models.DecimalField(max_digits=30, decimal_places=2, default=0)
    fees = models.DecimalField(max_digits=50, decimal_places=2, default=0)
    
    # Total amount
    total_amount = models.DecimalField(max_digits=100, decimal_places=2, blank=True, null=True)
    
    # Payment
    payment_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('paid', 'Paid'), ('financed', 'Financed'), ('refunded', 'Refunded')],
        default='pending'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    # Employee who handled the sale
    employee = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='handled_sales'
    )
    
    # Warranty information
    warranty_expiry = models.DateField(blank=True, null=True)
    warranty_terms = models.TextField(blank=True)
    
    # Trade-in information
    trade_in = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='trade_in_for', 
        help_text="Car traded in for this purchase"
    )
    trade_in_value = models.DecimalField(max_digits=50, decimal_places=2, blank=True, null=True)
    
    # Delivery information
    delivery_address = models.TextField(blank=True)
    delivery_notes = models.TextField(blank=True)
    
    def clean(self):
        # Validate that delivery_datetime is after purchase_datetime
        if self.delivery_datetime and self.delivery_datetime < self.purchase_datetime:
            raise ValidationError("Delivery date must be after purchase date.")
        
        # Validate that actual_delivery_datetime is after purchase_datetime
        if self.actual_delivery_datetime and self.actual_delivery_datetime < self.purchase_datetime:
            raise ValidationError("Actual delivery date must be after purchase date.")
        
        # Round decimal fields to 2 places
        if self.taxes:
            self.taxes = round(self.taxes, 2)
        if self.fees:
            self.fees = round(self.fees, 2)
        if self.total_amount:
            self.total_amount = round(self.total_amount, 2)
        if self.trade_in_value:
            self.trade_in_value = round(self.trade_in_value, 2)
    
    def save(self, *args, **kwargs):
        # Calculate total_amount if not provided
        if not self.total_amount:
            self.total_amount = round(self.purchase_price + self.taxes + self.fees, 2)
        
        # Auto-update status based on dates
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        
        if self.status == 'pending' and self.purchase_datetime < seven_days_ago:
            self.status = 'cancelled'
        elif self.status == 'shipped' and self.delivery_datetime and self.delivery_datetime < now:
            self.status = 'delivered'
        
        # ---  DELETION LOGIC (Only runs if Car is linked) ---
        old_status = None
        if self.pk and self.car:
            try:
                old_status = Purchase.objects.get(pk=self.pk).status
            except Purchase.DoesNotExist:
                pass
        car_to_delete = None
        if self.status == 'delivered' and old_status != 'delivered' and self.car:
            # 1. Store car reference
            car_to_delete = self.car
            
            # 2. Update car status to 'sold' (optional but good practice for history)
            car_to_delete.status = 'sold'
            car_to_delete.save()
            
            # 3. Unlink car from purchase BEFORE deleting the car (critical for ForeignKey integrity)
            self.car = None
        super().save(*args, **kwargs)
        if car_to_delete:
            car_to_delete.delete() # Executes SoftDeletionModel logic (is_deleted=True)
        
    def __str__(self):
        return f"{self.customer.name} - {self.car.make if self.car else 'DELETED CAR'} {self.car.model if self.car else ''}"
    
    @property
    def net_amount(self):
        """Calculate net amount after trade-in value"""
        trade_in_value = self.trade_in_value or 0
        return round(self.total_amount - trade_in_value, 2)
    
    def get_warranty_status(self):
        """Check if warranty is still valid"""
        if not self.warranty_expiry:
            return "No warranty"
        
        if self.warranty_expiry > timezone.now().date():
            return f"Valid until {self.warranty_expiry}"
        return "Expired"
    
    class Meta:
        ordering = ['-purchase_datetime']
        verbose_name = "Purchase"
        verbose_name_plural = "Purchases"

class UserProfile(TimeStampedModel, AuditableModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )]
    )
    whatsapp_number = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )]
    )
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = CloudinaryField('profile_picture', folder='profile_pics/')
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)
    delivery_address = models.TextField(blank=True)
    
    # Driver's license information
    drivers_license = models.CharField(max_length=50, blank=True)
    license_expiry = models.DateField(blank=True, null=True)
    license_image = CloudinaryField('license_image', folder='licenses/')
    
    # Payment methods (encrypted)
    payment_methods = models.JSONField(default=dict, blank=True)
    
    # User role
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('admin', 'Administrator'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    
    
    # Social Media Links
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    
    # Preferences
    newsletter_subscription = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    def has_driving_license(self):
        """Check if user has a valid driving license"""
        if not self.drivers_license or not self.license_expiry:
            return False
        return self.license_expiry > timezone.now().date()
    
    def get_active_rentals(self):
        """Get all active rentals for this user"""
        if hasattr(self.user, 'customer_account') and self.user.customer_account:
            return self.user.customer_account.get_active_rentals()
        return []
    
    def get_active_purchases(self):
        """Get all pending/processing purchases for this user"""
        if hasattr(self.user, 'customer_account') and self.user.customer_account:
            return self.user.customer_account.get_active_purchases()
        return []
    
    def clean(self):
        # Validate date_of_birth is not in the future
        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError("Date of birth cannot be in the future.")
        
        # Validate license expiry
        if self.license_expiry and self.license_expiry < timezone.now().date():
            raise ValidationError("Driver's license has expired.")
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

# Signal to create UserProfile when a User is created
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

# Service Booking Model
class ServiceBooking(TimeStampedModel, AuditableModel):
    SERVICE_TYPES = [
        ('diagnostic', 'Diagnostic Service'),
        ('repair', 'Repair Service'),
        ('upgrade', 'Upgrade Service'),
        ('consultation', 'Consultation Service'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Customer relationship
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='service_bookings',
        null=True,  # Allow null for anonymous bookings
        blank=True
    )
    
    # Customer information (kept for backward compatibility)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Car information
    car_make = models.CharField(max_length=100)
    car_model = models.CharField(max_length=100)
    car_year = models.IntegerField()
    
    # Service details
    preferred_date = models.DateField()
    description = models.TextField()
    
    # Additional fields
    notes = models.TextField(blank=True)
    whatsapp_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} - {self.get_service_type_display()} - {self.preferred_date}"
    
    def save(self, *args, **kwargs):
        # Auto-populate customer info if customer is set
        if self.customer:
            self.name = self.customer.name
            self.email = self.customer.email
            self.phone = self.customer.phone
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Service Booking"
        verbose_name_plural = "Service Bookings"

class CustomerRating(TimeStampedModel):
    SERVICE_TYPE_CHOICES = [
        ('rental', 'Rental'),
        ('purchase', 'Purchase'),
        ('service', 'Service'),
    ]
    
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES)
    
    # Generic foreign key to link to Rental, Purchase, or ServiceBooking
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    would_recommend = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('customer', 'content_type', 'object_id')
    
    def __str__(self):
        return f"{self.customer.name} - {self.get_service_type_display()} - {self.rating} stars"