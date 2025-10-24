from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from .models import (
    Car, SiteInfo, UserProfile, Customer, Rental, Purchase,
    ServiceBooking
)
from cloudinary import CloudinaryResource

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('make', 'model', 'year', 'car_type', 'status', 'for_rent', 'for_sale', 'featured', 'thumbnail')
    list_filter = ('car_type', 'transmission', 'engine_type', 'status', 'for_rent', 'for_sale', 'featured')
    search_fields = ('make', 'model', 'description', 'vin')
    list_editable = ('for_rent', 'for_sale', 'featured', 'status')
    fieldsets = (
        ('Basic Information', {
            'fields': ('make', 'model', 'year', 'vin', 'car_type', 'color', 'description', 'image', 'featured', 'status')
        }),
        ('Specifications', {
            'fields': ('mileage', 'transmission', 'engine_type', 'seats', 'fuel_efficiency')
        }),
        ('Pricing', {
            'fields': ('default_price', 'for_rent', 'rent_price', 'for_sale', 'sale_price')
        }),
    )
    readonly_fields = ('slug',)
    
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', 
                             obj.image.url)  # Cloudinary provides optimized URL
        return "No Image"
    thumbnail.short_description = 'Image'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('rentals', 'purchases')
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug',)
        return self.readonly_fields

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'has_valid_license', 'created_at', 'rental_count', 'purchase_count', 'service_count')
    search_fields = ('name', 'email', 'drivers_license')
    list_filter = ('created_at',)  # REMOVED 'has_valid_license' FROM HERE
    readonly_fields = ('created_at',)
    
    def has_valid_license(self, obj):
        return obj.has_valid_license()
    has_valid_license.boolean = True
    has_valid_license.short_description = 'Valid License'
    
    def rental_count(self, obj):
        count = obj.rentals.count()
        url = reverse('admin:car_rental_rental_changelist') + f'?customer__id__exact={obj.id}'
        return format_html('<a href="{}">{} Rentals</a>', url, count)
    
    def purchase_count(self, obj):
        count = obj.purchases.count()
        url = reverse('admin:car_rental_purchase_changelist') + f'?customer__id__exact={obj.id}'
        return format_html('<a href="{}">{} Purchases</a>', url, count)
    
    def service_count(self, obj):
        count = len(obj.get_service_history())
        return format_html('{} Services', count)
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('rentals', 'purchases')

@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ('customer', 'car', 'rental_datetime', 'return_datetime', 'daily_rate', 'total_amount', 'status', 'payment_status', 'is_late_fee_overridden')
    list_filter = ('status', 'payment_status', 'rental_datetime', 'override_late_fee')
    search_fields = ('customer__name', 'car__make', 'car__model', 'car__vin')
    date_hierarchy = 'rental_datetime'
    readonly_fields = ('late_fee', 'total_amount_due')
    
    fieldsets = (
        ('Rental Information', {
            'fields': ('customer', 'car', 'rental_datetime', 'return_datetime', 'actual_return_datetime')
        }),
        ('Location', {
            'fields': ('pickup_location', 'return_location')
        }),
        ('Pricing', {
            'fields': ('daily_rate', 'total_amount', 'late_fee', 'override_late_fee', 'manual_late_fee', 'total_amount_due')
        }),
        ('Status', {
            'fields': ('status', 'payment_status')
        }),
        ('Employee & Insurance', {
            'fields': ('employee', 'insurance_provider', 'insurance_policy')
        }),
    )
    
    def is_late_fee_overridden(self, obj):
        """Display whether late fee is overridden"""
        if obj.override_late_fee:
            return format_html('<span style="color: red;">✓ Manual</span>')
        return format_html('<span style="color: green;">Auto</span>')
    is_late_fee_overridden.short_description = 'Late Fee'
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        
        # Make manual_late_fee editable only when override_late_fee is True
        if obj and not obj.override_late_fee:
            readonly_fields += ('manual_late_fee',)
            
        return readonly_fields
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'car', 'employee')
    
    def response_change(self, request, obj):
        if "_return_car" in request.POST:
            obj.actual_return_datetime = timezone.now()
            obj.status = 'completed'
            obj.save()
            self.message_user(request, "Car has been returned successfully.")
            return JsonResponse({'status': 'success'})
        return super().response_change(request, obj)

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('customer', 'car', 'purchase_datetime', 'purchase_price', 'status', 'payment_status')
    list_filter = ('status', 'payment_status', 'purchase_datetime')
    search_fields = ('customer__name', 'car__make', 'car__model', 'car__vin')
    date_hierarchy = 'purchase_datetime'
    readonly_fields = ('net_amount',)
    
    fieldsets = (
        ('Purchase Information', {
            'fields': ('customer', 'car', 'purchase_datetime', 'delivery_datetime', 'actual_delivery_datetime')
        }),
        ('Pricing', {
            'fields': ('purchase_price', 'taxes', 'fees', 'total_amount', 'net_amount')
        }),
        ('Status', {
            'fields': ('status', 'payment_status')
        }),
        ('Employee', {
            'fields': ('employee',)
        }),
        ('Warranty', {
            'fields': ('warranty_expiry', 'warranty_terms')
        }),
        ('Trade-in', {
            'fields': ('trade_in', 'trade_in_value')
        }),
        ('Delivery', {
            'fields': ('delivery_address', 'delivery_notes')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'car', 'employee', 'trade_in')

# --- In admin.py ---

@admin.register(SiteInfo)
class SiteInfoAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'phone', 'email', 'updated_at')
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'tagline', 'description', 'logo', 'favicon')
        }),
        ('Contact Information', {
            'fields': ('address', 'phone', 'whatsapp_phone', 'email')
        }),
        ('Business Hours', {
            'fields': ('monday_hours', 'tuesday_hours', 'wednesday_hours', 'thursday_hours', 
                      'friday_hours', 'saturday_hours', 'sunday_hours')
        }),
        # Changed 'Social Media' section to only include Instagram and WhatsApp (which is under Contact Info)
        ('Social Links', {
            'fields': ('instagram_url',)
        }),
    )
    readonly_fields = ('updated_at',)
    
    def has_add_permission(self, request):
        # Only allow one instance of SiteInfo
        return not SiteInfo.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the SiteInfo
        return False

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'email', 'phone', 'has_valid_license', 'role', 'newsletter_subscription')
    list_filter = ('role', 'newsletter_subscription', 'email_notifications', 'sms_notifications', 'country')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'role', 'date_of_birth', 'profile_picture')
        }),
        ('Contact Information', {
            'fields': ('phone', 'address', 'city', 'state', 'zip_code', 'country')
        }),
        ('Driver\'s License', {
            'fields': ('drivers_license', 'license_expiry', 'license_image')
        }),
        ('Additional Information', {
            'fields': ('bio', 'website')
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url')
        }),
        ('Preferences', {
            'fields': ('newsletter_subscription', 'email_notifications', 'sms_notifications')
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name
    
    def email(self, obj):
        return obj.user.email
    
    def has_valid_license(self, obj):
        return obj.has_driving_license()
    has_valid_license.boolean = True
    has_valid_license.short_description = 'Valid License'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

# Automotive Service Admins

@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'service_type', 'car_make', 'car_model', 'preferred_date', 'status', 'whatsapp_sent', 'created_at')
    list_filter = ('service_type', 'status', 'whatsapp_sent', 'created_at')
    search_fields = ('name', 'email', 'phone', 'car_make', 'car_model', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Service Information', {
            'fields': ('service_type', 'status', 'preferred_date', 'description')
        }),
        ('Customer Information', {
            'fields': ('name', 'email', 'phone')
        }),
        ('Vehicle Information', {
            'fields': ('car_make', 'car_model', 'car_year')
        }),
        ('Additional Information', {
            'fields': ('notes', 'whatsapp_sent')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)