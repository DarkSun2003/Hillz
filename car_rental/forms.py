from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from .models import (
    UserProfile, SiteInfo, Car, Customer, Rental, Purchase,
    re, CustomerRating, ServiceBooking
)


# --- User & Profile Forms ---

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("This email is already associated with another account.")
        return email

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('phone', 'address', 'city', 'state', 'zip_code', 'country', 
                  'date_of_birth', 'profile_picture', 'bio', 'website',
                  'instagram_url', 'newsletter_subscription', 'email_notifications', 
                  'sms_notifications', 'drivers_license', 'license_expiry', 
                  'license_image', 'delivery_address', 'whatsapp_number')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'instagram_url': forms.URLInput(attrs={'class': 'form-control'}),
            'drivers_license': forms.TextInput(attrs={'class': 'form-control'}),
            'license_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'license_image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make license fields optional
        self.fields['drivers_license'].required = False
        self.fields['license_expiry'].required = False
        self.fields['license_image'].required = False
    
    def clean_license_expiry(self):
        license_expiry = self.cleaned_data.get('license_expiry')
        if license_expiry and license_expiry < timezone.now().date():
            raise ValidationError("Driver's license has expired.")
        return license_expiry

# --- Site Info Form ---

class SiteInfoForm(forms.ModelForm):
    """
    Form for editing the global SiteInfo settings.
    """
    class Meta:
        model = SiteInfo
        # Exclude the automatically managed fields
        exclude = ['created_by', 'updated_by']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'whatsapp_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'monday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'tuesday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'wednesday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'thursday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'friday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'saturday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'sunday_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'instagram_url': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'favicon': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

# --- Customer Forms ---

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ('name', 'email', 'phone', 'address', 'drivers_license', 'license_expiry', 'license_image')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'drivers_license': forms.TextInput(attrs={'class': 'form-control'}),
            'license_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'license_image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Make license fields optional
        self.fields['drivers_license'].required = False
        self.fields['license_expiry'].required = False
        self.fields['license_image'].required = False
        
        # If we have a user, pre-populate the name field
        if self.user and not self.initial.get('name'):
            self.initial['name'] = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Customer.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("This email is already associated with another customer.")
        return email

    def clean_license_expiry(self):
        license_expiry = self.cleaned_data.get('license_expiry')
        if license_expiry and license_expiry < timezone.now().date():
            raise ValidationError("Driver's license has expired.")
        return license_expiry

# --- Car Forms ---

class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = [
            'make', 'model', 'year', 'vin', 'default_price', 'car_type', 'color', 
            'mileage', 'transmission', 'engine_type', 'seats', 'fuel_efficiency',
            'for_rent', 'rent_price', 'for_sale', 'sale_price', 
            'image', 'description', 'featured', 'status'
        ]
        widgets = {
            'make': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'vin': forms.TextInput(attrs={'class': 'form-control'}),
            'default_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'car_type': forms.Select(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'mileage': forms.NumberInput(attrs={'class': 'form-control'}),
            'transmission': forms.Select(attrs={'class': 'form-control'}),
            'engine_type': forms.Select(attrs={'class': 'form-control'}),
            'seats': forms.NumberInput(attrs={'class': 'form-control'}),
            'fuel_efficiency': forms.NumberInput(attrs={'class': 'form-control'}),
            'rent_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Price per day'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sale price'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_vin(self):
        vin = self.cleaned_data.get('vin')
        if vin and not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', vin):
            raise ValidationError("Invalid VIN format.")
        return vin

# --- Rental Forms ---

class RentalForm(forms.ModelForm):
    rental_datetime = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
            'required': 'required'
        })
    )
    
    return_datetime = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
            'required': 'required'
        })
    )
    
    class Meta:
        model = Rental
        fields = [
            'rental_datetime', 
            'return_datetime', 
            'pickup_location',
            'insurance_provider',
            'insurance_policy'
        ]
        widgets = {
            'pickup_location': forms.TextInput(attrs={
                'class': 'form-control',
                'required': 'required',
                'placeholder': 'Enter pickup location'
            }),
            'insurance_provider': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Insurance provider name'
            }),
            'insurance_policy': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Policy number'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.car = kwargs.pop('car', None)
        super().__init__(*args, **kwargs)
        
        # Set initial rental datetime to now if not provided
        if not self.initial.get('rental_datetime'):
            # Format the datetime correctly for datetime-local input
            now = timezone.now()
            self.initial['rental_datetime'] = now.strftime('%Y-%m-%dT%H:%M')
    
    def clean(self):
        cleaned_data = super().clean()
        rental_datetime = cleaned_data.get('rental_datetime')
        return_datetime = cleaned_data.get('return_datetime')
        
        if rental_datetime and return_datetime:
            if return_datetime <= rental_datetime:
                raise forms.ValidationError("Return date must be after rental date.")
            
            # Check if car is available for these dates
            if self.car:
                overlapping_rentals = Rental.objects.filter(
                    car=self.car,
                    status__in=['active', 'pending'],
                    rental_datetime__lt=return_datetime,
                    return_datetime__gt=rental_datetime
                )
                
                if overlapping_rentals.exists():
                    raise forms.ValidationError("This car is not available for the selected dates.")
        
        return cleaned_data

class StaffRentalForm(forms.ModelForm):
    class Meta:
        model = Rental
        fields = [
            'customer', 'car', 'rental_datetime', 'return_datetime', 
            'daily_rate', 'total_amount',
            'payment_status', 'status', 'insurance_provider',
            'insurance_policy'
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'car': forms.Select(attrs={'class': 'form-control'}),
            'rental_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'return_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'daily_rate': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'insurance_provider': forms.TextInput(attrs={'class': 'form-control'}),
            'insurance_policy': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(StaffRentalForm, self).__init__(*args, **kwargs)

class RentalReturnForm(forms.ModelForm):
    class Meta:
        model = Rental
        fields = ['actual_return_datetime', 'status']
        widgets = {
            'actual_return_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow completed or overdue status
        self.fields['status'].choices = [
            ('completed', 'Completed'),
            ('overdue', 'Overdue'),
        ]

#purchase forms
class PurchaseForm(forms.ModelForm):
    """
    Form for creating or editing a purchase.
    """
    class Meta:
        model = Purchase
        fields = [
            'customer', 'car', 'purchase_datetime', 'delivery_datetime', 'actual_delivery_datetime',
            'purchase_price', 'taxes', 'fees', 'total_amount',
            'status', 'payment_status',
            'employee',
            'warranty_expiry', 'warranty_terms',
            'delivery_address', 'delivery_notes'
        ]
        widgets = {
            'purchase_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'delivery_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'actual_delivery_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'warranty_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'delivery_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'warranty_terms': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'car': forms.Select(attrs={'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taxes': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # If we have a car in the request, set initial values
        if self.request and self.request.GET.get('car_id'):
            try:
                car = Car.objects.get(pk=self.request.GET.get('car_id'))
                self.fields['purchase_price'].initial = car.get_sale_price
                self.fields['taxes'].initial = round(car.get_sale_price * Decimal('0.05'), 2)
                self.fields['fees'].initial = round(car.get_sale_price * Decimal('0.02'), 2)
                self.fields['total_amount'].initial = round(car.get_sale_price * Decimal('1.07'), 2)
            except Car.DoesNotExist:
                pass
    
    def clean_taxes(self):
        taxes = self.cleaned_data.get('taxes')
        if taxes is not None:
            # Round to 2 decimal places
            taxes = round(taxes, 2)
            # Validate that it doesn't exceed 2 decimal places
            if len(str(taxes).split('.')[-1]) > 2:
                raise forms.ValidationError("Ensure that there are no more than 2 decimal places.")
        return taxes

    def clean_fees(self):
        fees = self.cleaned_data.get('fees')
        if fees is not None:
            # Round to 2 decimal places
            fees = round(fees, 2)
            # Validate that it doesn't exceed 2 decimal places
            if len(str(fees).split('.')[-1]) > 2:
                raise forms.ValidationError("Ensure that there are no more than 2 decimal places.")
        return fees

    def clean_total_amount(self):
        total_amount = self.cleaned_data.get('total_amount')
        if total_amount is not None:
            # Round to 2 decimal places
            total_amount = round(total_amount, 2)
            # Validate that it doesn't exceed 2 decimal places
            if len(str(total_amount).split('.')[-1]) > 2:
                raise forms.ValidationError("Ensure that there are no more than 2 decimal places.")
        return total_amount
    
    def clean(self):
        cleaned_data = super().clean()
        delivery_datetime = cleaned_data.get('delivery_datetime')
        
        # Validate delivery date is in the future
        if delivery_datetime and delivery_datetime < timezone.now():
            raise ValidationError("Delivery date must be in the future.")
        
        return cleaned_data

# --- Service Forms ---



# --- Password Change Form ---

class PasswordChangeForm(DjangoPasswordChangeForm):
    """
    Inherits from Django's built-in PasswordChangeForm. 
    It only needs customization for Bootstrap widgets.
    """
    old_password = forms.CharField(
        label='Old password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
    )
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
    )
    new_password2 = forms.CharField(
        label='New password confirmation',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        #self.fields['old_password'].widget = self.old_password.widget
        #self.fields['new_password1'].widget = self.new_password1.widget
        #self.fields['new_password2'].widget = self.new_password2.widget
        
# Add these forms to your forms.py file

# forms.py
class ServiceBookingForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        fields = [
            'name', 'email', 'phone',
            'car_make', 'car_model', 'car_year',
            'preferred_date', 'description', 'service_type'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'car_make': forms.TextInput(attrs={'class': 'form-control'}),
            'car_model': forms.TextInput(attrs={'class': 'form-control'}),
            'car_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'preferred_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'service_type': forms.HiddenInput()
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.service_type = kwargs.pop('service_type', None)  # Get service_type from kwargs
        super().__init__(*args, **kwargs)
        
        # Set initial service type if provided
        if self.service_type and 'service_type' not in self.initial:
            self.initial['service_type'] = self.service_type
        
        # Pre-populate customer info if user is authenticated
        if self.user and self.user.is_authenticated:
            try:
                customer = self.user.customer_account
                if not self.initial.get('name'):
                    self.initial['name'] = customer.name
                if not self.initial.get('email'):
                    self.initial['email'] = customer.email
                if not self.initial.get('phone'):
                    self.initial['phone'] = customer.phone
            except (Customer.DoesNotExist, AttributeError):
                pass

class ServiceBookingUpdateForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        fields = ['service_type', 'status', 'name', 'email', 'phone', 
                 'car_make', 'car_model', 'car_year', 'preferred_date', 
                 'description', 'notes', 'whatsapp_sent']
        widgets = {
            'service_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'car_make': forms.TextInput(attrs={'class': 'form-control'}),
            'car_model': forms.TextInput(attrs={'class': 'form-control'}),
            'car_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'preferred_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'whatsapp_sent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CustomerRatingForm(forms.ModelForm):
    class Meta:
        model = CustomerRating
        fields = ['rating', 'comment', 'would_recommend']
        widgets = {
            'rating': forms.RadioSelect(choices=CustomerRating.RATING_CHOICES),
            'comment': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'would_recommend': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }