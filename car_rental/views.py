from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, DurationField, Max
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from datetime import datetime, timedelta
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_POST
from django import forms
from decimal import Decimal 
from .models import (
    Car, SiteInfo, Customer, UserProfile, Rental, Purchase, User, ServiceBooking, CustomerRating
)
from .forms import (
    CarForm, SiteInfoForm, PasswordChangeForm, UserForm, UserProfileForm,
    CustomerForm, RentalForm, RentalReturnForm, PurchaseForm,
    ServiceBookingForm, ServiceBookingUpdateForm, CustomerRatingForm, StaffRentalForm
)
from .utils import send_rental_confirmation_email, send_purchase_confirmation_email
from urllib.parse import quote

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging

logger = logging.getLogger(__name__)


# Helper functions
def is_staff_user(user):
    return user.is_authenticated and user.is_staff

def is_manager(user):
    return user.is_authenticated and user.is_staff and user.profile.role in ['manager', 'admin']

# --- WHATSAPP C2O HELPER ---
def generate_whatsapp_url(site_info, item_type, item_title):
    """Generates a WhatsApp URL for the site owner."""
    if not site_info or not site_info.whatsapp_phone:
        return None
    
    phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
    message = quote(f"Hello, I just submitted a new {item_type} request on Hillz Exquisites. Item: {item_title}. Please advise on the next steps for payment.")
    return f"https://wa.me/{phone}?text={message}"

# --- PUBLIC FACING VIEWS ---

class HomeView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        if not site_info:
            site_info = SiteInfo()
        
        # Filter out soft-deleted cars for public listing
        available_cars = Car.objects.filter(is_deleted=False, status__in=['available', 'rented', 'in_service'])
        
        # Get featured cars or a fallback of all cars
        featured_cars = available_cars.filter(featured=True)[:6] 
        if not featured_cars.exists():
            featured_cars = available_cars.order_by('-year')[:6]
        
        # Get all ratings
        ratings = CustomerRating.objects.all()
        
        # Overall rating
        overall_rating = 0
        if ratings.exists():
            total_rating = sum(rating.rating for rating in ratings)
            overall_rating = round(total_rating / ratings.count(), 1)
        
        # Total reviews
        total_reviews = ratings.count()
        
        # Satisfaction rate (percentage of 4+ star ratings)
        satisfaction_count = ratings.filter(rating__gte=4).count()
        satisfaction_rate = round((satisfaction_count / total_reviews * 100), 0) if total_reviews > 0 else 0
        
        # Recent reviews
        recent_reviews = ratings.order_by('-created_at')[:5]
        
        context = {
            'site_info': site_info,
            'featured_cars': featured_cars,
            'cars': available_cars[:12],
            'overall_rating': overall_rating,
            'total_reviews': total_reviews,
            'satisfaction_rate': satisfaction_rate,
            'recent_reviews': recent_reviews,
        }
        
        return render(request, 'home.html', context)

class CarListView(ListView):
    model = Car
    template_name = 'all_cars.html'
    context_object_name = 'cars'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False).exclude(status='sold')
        
        # Handle search query
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(make__icontains=query) | 
                Q(model__icontains=query) |
                Q(description__icontains=query) |
                Q(vin__icontains=query)
            )
        
        # Filter by car type if provided
        car_type = self.request.GET.get('type')
        if car_type:
            queryset = queryset.filter(car_type=car_type)
        
        # Filter by availability (rent or sale)
        availability = self.request.GET.get('availability')
        if availability == 'rent':
            queryset = queryset.filter(for_rent=True)
        elif availability == 'sale':
            queryset = queryset.filter(for_sale=True)
        
        # Handle sorting
        sort_by = self.request.GET.get('sort')
        if sort_by == 'make':
            queryset = queryset.order_by('make')
        elif sort_by == 'year':
            queryset = queryset.order_by('-year')
        elif sort_by == 'price':
            queryset = queryset.order_by('default_price')
        else:
            # Default sorting
            queryset = queryset.order_by('-year', 'make', 'model')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['car_types'] = Car.CAR_TYPES
        
        # Build current query string for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['current_query'] = query_params.urlencode()
        
        return context


class CarDetailView(DetailView):
    model = Car
    template_name = 'car_detail.html'
    context_object_name = 'car'
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False).select_related('created_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Calculate weekly and monthly rates if car is for rent
        if self.object.for_rent:
            daily_rate = self.object.get_rent_price
            context['daily_rate_unformatted'] = daily_rate
            context['weekly_rate_unformatted'] = daily_rate * 7
            context['monthly_rate_unformatted'] = daily_rate * 30
            context['weekly_rate'] = daily_rate * 7 
            context['monthly_rate'] = daily_rate * 30
        
        # Calculate discount information if car is for sale
        if self.object.for_sale and self.object.sale_price and self.object.default_price:
            discount = self.object.default_price - self.object.sale_price
            context['discount_amount_unformatted'] = discount
            context['discount_percentage'] = round((discount / self.object.default_price) * 100, 1)
            context['sale_price_unformatted'] = self.object.get_sale_price
        
        # Get similar cars based on make and model
        context['similar_cars'] = Car.objects.filter(
            Q(make=self.object.make) | Q(model=self.object.model)
        ).exclude(pk=self.object.pk).filter(is_deleted=False, status__in=['available', 'rented', 'in_service'])[:3]
        
        # Check if user has already rented this car
        if self.request.user.is_authenticated:
            try:
                customer = Customer.objects.get(email=self.request.user.email)
                context['has_rented'] = Rental.objects.filter(customer=customer, car=self.object).exists()
            except Customer.DoesNotExist:
                context['has_rented'] = False
        
        return context

class RentCarListView(ListView):
    model = Car
    template_name = 'rent_cars.html'
    context_object_name = 'cars'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False, for_rent=True).exclude(status='sold')
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(make__icontains=query) |
                Q(model__icontains=query) |
                Q(description__icontains=query) |
                Q(vin__icontains=query)
            )

        car_type = self.request.GET.get('type')
        if car_type:
            queryset = queryset.filter(car_type=car_type)

        return queryset.order_by('make')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['car_types'] = Car.CAR_TYPES

        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['current_query'] = query_params.urlencode()
        
        # Calculate weekly rates for display
        for car in context['cars']:
            car.weekly_rate = car.get_rent_price * 6
        
        return context

class SaleCarListView(ListView):
    model = Car
    template_name = 'sale_cars.html'
    context_object_name = 'cars'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False, for_sale=True).exclude(status='sold')

        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(make__icontains=query) |
                Q(model__icontains=query) |
                Q(description__icontains=query) |
                Q(vin__icontains=query)
            )

        car_type = self.request.GET.get('type')
        if car_type:
            queryset = queryset.filter(car_type=car_type)

        return queryset.order_by('make')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['car_types'] = Car.CAR_TYPES

        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['current_query'] = query_params.urlencode()

        return context

class SearchView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        
        query = request.GET.get('q')
        car_type = request.GET.get('type')
        
        cars = Car.objects.filter(is_deleted=False).exclude(status='sold')
        
        if query:
            cars = cars.filter(
                Q(make__icontains=query) | 
                Q(model__icontains=query) |
                Q(description__icontains=query) |
                Q(vin__icontains=query)
            )
        
        if car_type:
            cars = cars.filter(car_type=car_type)
        
        # Add pagination
        paginator = Paginator(cars, 12)
        page_number = request.GET.get('page')
        cars = paginator.get_page(page_number)
        
        context = {
            'site_info': site_info,
            'cars': cars,
            'query': query,
            'car_type': car_type
        }
        
        return render(request, 'search_results.html', context)

class AboutView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        if not site_info:
            site_info = SiteInfo()
        
        # Get featured cars or a fallback of all cars
        featured_cars = Car.objects.filter(featured=True, status='available')[:6] 
        if not featured_cars.exists():
            featured_cars = Car.objects.filter(status='available').order_by('-year')[:6]
        
        # Get all available cars for the featured section
        cars = Car.objects.filter(status='available')[:12]
        
        # Get all ratings
        ratings = CustomerRating.objects.all()
        
        # Overall rating
        overall_rating = 0
        if ratings.exists():
            total_rating = sum(rating.rating for rating in ratings)
            overall_rating = round(total_rating / ratings.count(), 1)
        
        # Total reviews
        total_reviews = ratings.count()
        
        # Satisfaction rate (percentage of 4+ star ratings)
        satisfaction_count = ratings.filter(rating__gte=4).count()
        satisfaction_rate = round((satisfaction_count / total_reviews * 100), 0) if total_reviews > 0 else 0
        
        # Service quality (based on average rating)
        if overall_rating >= 4.5:
            service_quality = "A+"
        elif overall_rating >= 4.0:
            service_quality = "A"
        elif overall_rating >= 3.5:
            service_quality = "B+"
        elif overall_rating >= 3.0:
            service_quality = "B"
        else:
            service_quality = "C"
        
        # Rating breakdown
        rating_breakdown = {
            'five': 0,
            'four': 0,
            'three': 0,
            'two': 0,
            'one': 0
        }
        
        if total_reviews > 0:
            rating_breakdown['five'] = round((ratings.filter(rating=5).count() / total_reviews) * 100)
            rating_breakdown['four'] = round((ratings.filter(rating=4).count() / total_reviews) * 100)
            rating_breakdown['three'] = round((ratings.filter(rating=3).count() / total_reviews) * 100)
            rating_breakdown['two'] = round((ratings.filter(rating=2).count() / total_reviews) * 100)
            rating_breakdown['one'] = round((ratings.filter(rating=1).count() / total_reviews) * 100)
        
        # Recent reviews
        recent_reviews = ratings.order_by('-created_at')[:5]
        
        context = {
            'site_info': site_info,
            'featured_cars': featured_cars,
            'cars': cars,
            'overall_rating': overall_rating,
            'total_reviews': total_reviews,
            'satisfaction_rate': satisfaction_rate,
            'service_quality': service_quality,
            'rating_breakdown': rating_breakdown,
            'recent_reviews': recent_reviews,
        }
        
        return render(request, 'about.html', context)

class ContactView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        context = {'site_info': site_info}
        return render(request, 'contact.html', context)
    
    def post(self, request):
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Process contact form (send email, save to database, etc.)
        # This is a placeholder for actual contact form processing
        
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('car_rental:contact')

# --- INDIVIDUAL SERVICE BOOKING VIEWS ---
class BookDiagnosticServiceView(LoginRequiredMixin, CreateView):
    model = ServiceBooking
    form_class = ServiceBookingForm
    template_name = 'book_diagnostic_service.html'
    # Update the success URL
    success_url = reverse_lazy('car_rental:whatsapp_diagnostic_success')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['service_type'] = 'diagnostic'
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['service_type'] = 'diagnostic'
        return context
    
    def form_valid(self, form):
        booking = form.save(commit=False)
        
        # Associate with customer if user is authenticated
        if self.request.user.is_authenticated:
            try:
                customer = self.request.user.customer_account
                booking.customer = customer
            except (Customer.DoesNotExist, AttributeError):
                # If customer doesn't exist, create one
                customer = Customer.objects.create(
                    name=f"{self.request.user.first_name} {self.request.user.last_name}".strip() or self.request.user.username,
                    email=self.request.user.email,
                    user=self.request.user
                )
                booking.customer = customer
        
        # Generate WhatsApp URL for diagnostic service
        site_info = SiteInfo.objects.first()
        if site_info and site_info.whatsapp_phone:
            phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
            message = quote(
                f"Hello, I'd like to book a Diagnostic Service for my vehicle.\n\n"
                f"Name: {booking.name}\n"
                f"Email: {booking.email}\n"
                f"Phone: {booking.phone}\n"
                f"Car: {booking.car_year} {booking.car_make} {booking.car_model}\n"
                f"Preferred Date: {booking.preferred_date}\n"
                f"Description: {booking.description}\n\n"
                f"I'm experiencing some issues with my vehicle and would like to schedule a diagnostic service to identify the problem.\n\n"
                f"Please advise on the next steps for scheduling my diagnostic appointment."
            )
            
            booking.whatsapp_sent = True
            booking.save()
            
            whatsapp_url = f"https://wa.me/{phone}?text={message}"
            
            # Store booking info in session for success page
            self.request.session['booking_info'] = {
                'service_type': 'diagnostic',
                'booking_id': booking.id,
                'redirect_url': whatsapp_url
            }
            
            messages.success(self.request, 'Your diagnostic service booking has been submitted successfully!')
            return redirect('car_rental:whatsapp_diagnostic_success')
        else:
            booking.save()
            messages.success(self.request, 'Your diagnostic service booking has been submitted successfully!')
            return redirect('car_rental:services_overview')

# Apply the same pattern to the other service booking views
class BookRepairServiceView(LoginRequiredMixin, CreateView):
    model = ServiceBooking
    form_class = ServiceBookingForm
    template_name = 'book_repair_service.html'
    success_url = reverse_lazy('car_rental:whatsapp_repair_success')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['service_type'] = 'repair'
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['service_type'] = 'repair'
        return context
    
    def form_valid(self, form):
        booking = form.save(commit=False)
        
        # Associate with customer if user is authenticated
        if self.request.user.is_authenticated:
            try:
                customer = self.request.user.customer_account
                booking.customer = customer
            except (Customer.DoesNotExist, AttributeError):
                # If customer doesn't exist, create one
                customer = Customer.objects.create(
                    name=f"{self.request.user.first_name} {self.request.user.last_name}".strip() or self.request.user.username,
                    email=self.request.user.email,
                    user=self.request.user
                )
                booking.customer = customer
        
        # Generate WhatsApp URL for repair service
        site_info = SiteInfo.objects.first()
        if site_info and site_info.whatsapp_phone:
            phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
            message = quote(
                f"Hello, I'd like to book a Repair Service for my vehicle.\n\n"
                f"Name: {booking.name}\n"
                f"Email: {booking.email}\n"
                f"Phone: {booking.phone}\n"
                f"Car: {booking.car_year} {booking.car_make} {booking.car_model}\n"
                f"Preferred Date: {booking.preferred_date}\n"
                f"Description: {booking.description}\n\n"
                f"My vehicle needs repair work and I would like to schedule an appointment with your technicians.\n\n"
                f"Please advise on the next steps for scheduling my repair service."
            )
            
            booking.whatsapp_sent = True
            booking.save()
            
            whatsapp_url = f"https://wa.me/{phone}?text={message}"
            
            # Store booking info in session for success page
            self.request.session['booking_info'] = {
                'service_type': 'repair',
                'booking_id': booking.id,
                'redirect_url': whatsapp_url
            }
            
            messages.success(self.request, 'Your repair service booking has been submitted successfully!')
            return redirect('car_rental:whatsapp_repair_success')
        else:
            booking.save()
            messages.success(self.request, 'Your repair service booking has been submitted successfully!')
            return redirect('car_rental:services_overview')

class BookUpgradeServiceView(LoginRequiredMixin, CreateView):
    model = ServiceBooking
    form_class = ServiceBookingForm
    template_name = 'book_upgrade_service.html'
    success_url = reverse_lazy('car_rental:whatsapp_upgrade_success')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['service_type'] = 'upgrade'
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['service_type'] = 'upgrade'
        return context
    
    def form_valid(self, form):
        booking = form.save(commit=False)
        
        # Associate with customer if user is authenticated
        if self.request.user.is_authenticated:
            try:
                customer = self.request.user.customer_account
                booking.customer = customer
            except (Customer.DoesNotExist, AttributeError):
                # If customer doesn't exist, create one
                customer = Customer.objects.create(
                    name=f"{self.request.user.first_name} {self.request.user.last_name}".strip() or self.request.user.username,
                    email=self.request.user.email,
                    user=self.request.user
                )
                booking.customer = customer
        
        # Generate WhatsApp URL for upgrade service
        site_info = SiteInfo.objects.first()
        if site_info and site_info.whatsapp_phone:
            phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
            message = quote(
                f"Hello, I'd like to book an Upgrade Service for my vehicle.\n\n"
                f"Name: {booking.name}\n"
                f"Email: {booking.email}\n"
                f"Phone: {booking.phone}\n"
                f"Car: {booking.car_year} {booking.car_make} {booking.car_model}\n"
                f"Preferred Date: {booking.preferred_date}\n"
                f"Description: {booking.description}\n\n"
                f"I'm interested in performance upgrades and would like to discuss available options for my vehicle.\n\n"
                f"Please advise on the next steps for scheduling my upgrade consultation."
            )
            
            booking.whatsapp_sent = True
            booking.save()
            
            whatsapp_url = f"https://wa.me/{phone}?text={message}"
            
            # Store booking info in session for success page
            self.request.session['booking_info'] = {
                'service_type': 'upgrade',
                'booking_id': booking.id,
                'redirect_url': whatsapp_url
            }
            
            messages.success(self.request, 'Your upgrade service booking has been submitted successfully!')
            return redirect('car_rental:whatsapp_upgrade_success')
        else:
            booking.save()
            messages.success(self.request, 'Your upgrade service booking has been submitted successfully!')
            return redirect('car_rental:services_overview')

class BookConsultationServiceView(LoginRequiredMixin, CreateView):
    model = ServiceBooking
    form_class = ServiceBookingForm
    template_name = 'book_consultation_service.html'
    success_url = reverse_lazy('car_rental:whatsapp_consultation_success')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['service_type'] = 'consultation'
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['service_type'] = 'consultation'
        return context
    
    def form_valid(self, form):
        booking = form.save(commit=False)
        
        # Associate with customer if user is authenticated
        if self.request.user.is_authenticated:
            try:
                customer = self.request.user.customer_account
                booking.customer = customer
            except (Customer.DoesNotExist, AttributeError):
                # If customer doesn't exist, create one
                customer = Customer.objects.create(
                    name=f"{self.request.user.first_name} {self.request.user.last_name}".strip() or self.request.user.username,
                    email=self.request.user.email,
                    user=self.request.user
                )
                booking.customer = customer
        
        # Generate WhatsApp URL for consultation service
        site_info = SiteInfo.objects.first()
        if site_info and site_info.whatsapp_phone:
            phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
            message = quote(
                f"Hello, I'd like to book a Consultation Service with your automotive experts.\n\n"
                f"Name: {booking.name}\n"
                f"Email: {booking.email}\n"
                f"Phone: {booking.phone}\n"
                f"Car: {booking.car_year} {booking.car_make} {booking.car_model}\n"
                f"Preferred Date: {booking.preferred_date}\n"
                f"Description: {booking.description}\n\n"
                f"I would like to discuss my vehicle's needs and get professional advice on maintenance, upgrades, or other services.\n\n"
                f"Please advise on the next steps for scheduling my consultation."
            )
            
            booking.whatsapp_sent = True
            booking.save()
            
            whatsapp_url = f"https://wa.me/{phone}?text={message}"
            
            # Store booking info in session for success page
            self.request.session['booking_info'] = {
                'service_type': 'consultation',
                'booking_id': booking.id,
                'redirect_url': whatsapp_url
            }
            
            messages.success(self.request, 'Your consultation service booking has been submitted successfully!')
            return redirect('car_rental:whatsapp_consultation_success')
        else:
            booking.save()
            messages.success(self.request, 'Your consultation service booking has been submitted successfully!')
            return redirect('car_rental:services_overview')

class WhatsAppDiagnosticSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'whatsapp_diagnostic_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_info = self.request.session.get('booking_info', {})
        
        if booking_info.get('service_type') == 'diagnostic':
            try:
                booking = ServiceBooking.objects.get(id=booking_info.get('booking_id'))
                context['booking'] = booking
                context['whatsapp_url'] = booking_info.get('redirect_url')
            except ServiceBooking.DoesNotExist:
                pass
        
        context['site_info'] = SiteInfo.objects.first()
        return context

class WhatsAppRepairSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'whatsapp_repair_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_info = self.request.session.get('booking_info', {})
        
        if booking_info.get('service_type') == 'repair':
            try:
                booking = ServiceBooking.objects.get(id=booking_info.get('booking_id'))
                context['booking'] = booking
                context['whatsapp_url'] = booking_info.get('redirect_url')
            except ServiceBooking.DoesNotExist:
                pass
        
        context['site_info'] = SiteInfo.objects.first()
        return context

class WhatsAppUpgradeSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'whatsapp_upgrade_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_info = self.request.session.get('booking_info', {})
        
        if booking_info.get('service_type') == 'upgrade':
            try:
                booking = ServiceBooking.objects.get(id=booking_info.get('booking_id'))
                context['booking'] = booking
                context['whatsapp_url'] = booking_info.get('redirect_url')
            except ServiceBooking.DoesNotExist:
                pass
        
        context['site_info'] = SiteInfo.objects.first()
        return context

class WhatsAppConsultationSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'whatsapp_consultation_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_info = self.request.session.get('booking_info', {})
        
        if booking_info.get('service_type') == 'consultation':
            try:
                booking = ServiceBooking.objects.get(id=booking_info.get('booking_id'))
                context['booking'] = booking
                context['whatsapp_url'] = booking_info.get('redirect_url')
            except ServiceBooking.DoesNotExist:
                pass
        
        context['site_info'] = SiteInfo.objects.first()
        return context

class WhatsAppSuccessView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        purchase_id = request.session.get('last_purchase_id')
        whatsapp_url = request.session.get('whatsapp_url')
        
        purchase = None
        if purchase_id:
            try:
                purchase = Purchase.objects.get(id=purchase_id)
            except Purchase.DoesNotExist:
                pass
        
        context = {
            'site_info': site_info,
            'purchase': purchase,
            'whatsapp_url': whatsapp_url,
        }
        
        # Use different template for purchases vs service bookings
        if purchase:
            return render(request, 'whatsapp_purchase_success.html', context)
        else:
            return render(request, 'whatsapp_success.html', context)

# Admin views for managing service bookings

class ServiceBookingListView(UserPassesTestMixin, ListView):
    model = ServiceBooking
    template_name = 'admin/service_booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by service type
        service_type = self.request.GET.get('service_type')
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['service_types'] = ServiceBooking.SERVICE_TYPES
        context['status_choices'] = ServiceBooking.STATUS_CHOICES
        
        # Build current query string for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['current_query'] = query_params.urlencode()
        
        return context

class ServiceBookingDetailView(UserPassesTestMixin, DetailView):
    model = ServiceBooking
    template_name = 'admin/service_booking_detail.html'
    context_object_name = 'booking'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context

class ServiceBookingUpdateView(UserPassesTestMixin, UpdateView):
    model = ServiceBooking
    form_class = ServiceBookingUpdateForm
    template_name = 'admin/service_booking_update.html'
    success_url = reverse_lazy('car_rental:service_booking_list')
    
    def test_func(self):
        return self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, 'Service booking updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def update_service_booking_status(request, pk):
    booking = get_object_or_404(ServiceBooking, pk=pk)
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')
    
    if new_status in dict(ServiceBooking.STATUS_CHOICES):
        booking.status = new_status
        if notes:
            booking.notes = notes
        booking.save()
        messages.success(request, f'Booking status updated to {booking.get_status_display()}.')
    else:
        messages.error(request, 'Invalid status.')
    
    return redirect('car_rental:service_booking_detail', pk=booking.pk)

# --- AUTHENTICATION VIEWS ---

class LoginView(View):
    def get(self, request):
        form = AuthenticationForm()
        site_info = SiteInfo.objects.first()
        context = {
            'form': form,
            'site_info': site_info
        }
        return render(request, 'login.html', context)
    
    def post(self, request):
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user() 
            
            if user is not None:
                login(request, user) 
                
                messages.success(request, f"Welcome back, {user.username}!")
                
                next_url = request.GET.get('next', reverse('car_rental:profile'))
                
                return redirect(next_url) 
                
            messages.error(request, 'Invalid username or password.')
        
        else:
            messages.error(request, 'Invalid username or password. Please check your credentials.')
        
        site_info = SiteInfo.objects.first()
        context = {
            'form': form,
            'site_info': site_info
        }
        return render(request, 'login.html', context)

class RegisterView(View):
    """Handle user registration"""
    template_name = 'register.html'
    
    def get(self, request):
        """Display registration form"""
        form = UserCreationForm()
        site_info = SiteInfo.objects.first()
        context = {
            'form': form,
            'site_info': site_info
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Process registration form submission"""
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create a Customer record if email is provided
            if user.email:
                customer, created = Customer.objects.get_or_create(
                    email=user.email,
                    defaults={
                        'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'user': user
                    }
                )
                
                # Link the customer to the user
                user.customer_profile = customer
                user.save()
            
            # Create UserProfile if it doesn't exist
            UserProfile.objects.get_or_create(user=user)
            
            # Authenticate and login the user
            user = authenticate(
                username=form.cleaned_data.get('username'), 
                password=form.cleaned_data.get('password1')
            )
            if user:
                login(request, user)
                messages.success(request, 'Registration successful. Welcome to Hillz Exquisite!')
            else:
                messages.warning(request, 'Registration successful, but automatic login failed. Please log in.')
            
            return redirect('car_rental:profile') 
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
        
        site_info = SiteInfo.objects.first()
        context = {
            'form': form,
            'site_info': site_info
        }
        return render(request, self.template_name, context)

# --- USER PROFILE VIEWS ---

@login_required
def profile(request):
    # Ensure UserProfile exists
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Get or create Customer information
    try:
        customer = request.user.customer_account
        rentals = Rental.objects.filter(customer=customer).order_by('-rental_datetime')
        purchases = Purchase.objects.filter(customer=customer).order_by('-purchase_datetime')
    except Customer.DoesNotExist:
        # Create customer account if it doesn't exist
        customer = Customer.objects.create(
            name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            email=request.user.email,
            user=request.user
        )
        rentals = Rental.objects.none()
        purchases = Purchase.objects.none()
        messages.info(request, 'A customer account has been created for you.')

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        customer_form = CustomerForm(request.POST, request.FILES, instance=customer, user=request.user)

        if user_form.is_valid() and profile_form.is_valid() and customer_form.is_valid():
            try:
                user_form.save()
                profile_form.save()
                customer_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('car_rental:profile')
            except Exception as e:
                messages.error(request, f'An error occurred while updating your profile: {str(e)}')
                logger.error(f"Profile update error: {e}")
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=profile)
        customer_form = CustomerForm(instance=customer, user=request.user)
    
    # Calculate statistics
    total_rentals = rentals.count() if rentals else 0
    total_purchases = purchases.count() if purchases else 0
    
    rental_spent = rentals.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
    purchase_spent = purchases.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
    total_spent = rental_spent + purchase_spent
    
    context = {
        'profile': profile,
        'customer': customer,
        'rentals': rentals[:5],
        'purchases': purchases[:5],
        'user_form': user_form,
        'profile_form': profile_form,
        'customer_form': customer_form,
        'site_info': SiteInfo.objects.first(),
        'stats': {
            'total_rentals': total_rentals,
            'total_purchases': total_purchases,
            'rental_spent': rental_spent,
            'purchase_spent': purchase_spent,
            'total_spent': total_spent,
        }
    }
    
    return render(request, 'profile.html', context)

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('car_rental:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    site_info = SiteInfo.objects.first()
    context = {
        'form': form,
        'site_info': site_info
    }
    return render(request, 'change_password.html', context)

@login_required
def delete_account(request):
    if request.method == 'POST':
        if request.POST.get('confirm_delete') == 'yes':
            user = request.user
            username = user.username
            logout(request)
            user.delete()
            messages.success(request, f'Account "{username}" has been successfully deleted.')
            return redirect('car_rental:home')
        else:
            messages.error(request, 'Account deletion was not confirmed.')
            return redirect('car_rental:profile')
    
    site_info = SiteInfo.objects.first()
    context = {'site_info': site_info}
    return render(request, 'delete_account.html', context)

class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'profile_edit.html'
    success_url = reverse_lazy('car_rental:profile')
    
    def get_object(self):
        return self.request.user.profile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        context['user_form'] = UserForm(instance=self.request.user)
        
        # Get customer form if customer exists
        try:
            customer = self.request.user.customer_account
            context['customer_form'] = CustomerForm(instance=customer)
        except (Customer.DoesNotExist, AttributeError):
            context['customer_form'] = None
        
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        user_form = UserForm(request.POST, instance=request.user)
        
        # Get customer form if customer exists
        try:
            customer = request.user.customer_account
            customer_form = CustomerForm(request.POST, request.FILES, instance=customer)
        except (Customer.DoesNotExist, AttributeError):
            customer_form = None
        
        if form.is_valid() and user_form.is_valid():
            try:
                # Save user form
                user_form.save()
                
                # Save profile form
                self.object = form.save()
                
                # Save customer form if it exists
                if customer_form and customer_form.is_valid():
                    customer_form.save()
                
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect(self.get_success_url())
            except Exception as e:
                messages.error(request, f'An error occurred while updating your profile: {str(e)}')
                logger.error(f"Profile edit error: {e}")
        else:
            # Collect form errors
            error_messages = []
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")
            if not user_form.is_valid():
                for field, errors in user_form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")
            if customer_form and not customer_form.is_valid():
                for field, errors in customer_form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")
            
            # Add non-field errors if any
            if form.non_field_errors:
                error_messages.extend(list(form.non_field_errors))
            if user_form.non_field_errors:
                error_messages.extend(list(user_form.non_field_errors))
            if customer_form and customer_form.non_field_errors:
                error_messages.extend(list(customer_form.non_field_errors))
            
            messages.error(request, 'Please correct the errors below.')
            for error in error_messages:
                messages.error(request, error)
        
        return self.render_to_response(self.get_context_data(form=form, user_form=user_form, customer_form=customer_form))

class MyRentalsView(LoginRequiredMixin, ListView):
    model = Rental
    template_name = 'my_rentals.html'
    context_object_name = 'rentals'
    paginate_by = 10
    
    def get_queryset(self):
        try:
            customer = self.request.user.customer_account
            return Rental.objects.filter(customer=customer).select_related('car', 'employee').order_by('-rental_datetime')
        except (Customer.DoesNotExist, AttributeError):
            return Rental.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Get the full queryset for statistics calculation
        try:
            customer = self.request.user.customer_account
            # Create a new queryset for statistics to avoid slicing issues
            full_rentals = Rental.objects.filter(customer=customer)
            
            # Calculate stats
            context['total_rentals'] = full_rentals.count()
            context['active_rentals'] = full_rentals.filter(status__in=['active', 'overdue']).count()
            
            total_spent = full_rentals.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
            context['total_spent'] = total_spent
            
            # Get ratings for rentals to show if the user has already rated it
            if self.request.user.is_authenticated:
                try:
                    customer = self.request.user.customer_account
                    # Get the IDs of rentals that have been rated by this customer
                    rated_rentals = CustomerRating.objects.filter(
                        customer=customer,
                        service_type='rental'
                    ).values_list('object_id', flat=True)
                    context['rated_rentals'] = list(rated_rentals)
                except (Customer.DoesNotExist, AttributeError):
                    context['rated_rentals'] = []
                
        except (Customer.DoesNotExist, AttributeError):
            context['total_rentals'] = 0
            context['active_rentals'] = 0
            context['total_spent'] = 0
            context['rated_rentals'] = []
                
        return context

class MyPurchasesView(LoginRequiredMixin, ListView):
    model = Purchase
    template_name = 'my_purchases.html'
    context_object_name = 'purchases'
    paginate_by = 10
    
    def get_queryset(self):
        try:
            customer = self.request.user.customer_account
            # Get the base queryset without slicing
            queryset = Purchase.objects.filter(customer=customer).select_related('car').order_by('-purchase_datetime')
            return queryset
        except (Customer.DoesNotExist, AttributeError):
            return Purchase.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Get the full queryset for statistics calculation (before pagination)
        try:
            customer = self.request.user.customer_account
            # Create a new queryset for statistics to avoid slicing issues
            full_purchases = Purchase.objects.filter(customer=customer)
            
            # Calculate stats from the full queryset
            context['total_purchases'] = full_purchases.count()
            context['delivered_purchases'] = full_purchases.filter(status='delivered').count()
            
            total_spent = full_purchases.aggregate(total=Sum('total_amount'))['total'] or 0
            context['total_spent'] = total_spent
            
            # Get ratings for purchases to show if the user has already rated it
            rated_purchases = CustomerRating.objects.filter(
                customer=customer,
                service_type='purchase'
            ).values_list('object_id', flat=True)
            context['rated_purchases'] = list(rated_purchases)
            
        except (Customer.DoesNotExist, AttributeError):
            context['total_purchases'] = 0
            context['delivered_purchases'] = 0
            context['total_spent'] = 0
            context['rated_purchases'] = []
                
        return context

class PurchasesListView(UserPassesTestMixin, ListView):
    model = Purchase
    template_name = 'admin/purchases_list.html'
    context_object_name = 'purchases'
    paginate_by = 20
    
    def test_func(self):
        # Only allow superusers to view all purchases
        return self.request.user.is_superuser
    
    def get_queryset(self):
        return Purchase.objects.all().select_related('customer', 'car', 'employee').order_by('-purchase_datetime')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context

# --- STAFF/ADMIN VIEWS ---

@login_required
@user_passes_test(is_staff_user)
def site_info_edit(request):
    site_info, created = SiteInfo.objects.get_or_create(pk=1)
    
    if request.method == 'POST':
        form = SiteInfoForm(request.POST, request.FILES, instance=site_info)
        if form.is_valid():
            form.save()
            messages.success(request, 'Site information updated successfully.')
            return redirect('car_rental:site_info_edit') 
        messages.error(request, 'Error updating site information.')
    else:
        form = SiteInfoForm(instance=site_info)
    
    context = {'form': form, 'site_info': site_info}
    return render(request, 'site_info_edit.html', context)

class AddCarView(UserPassesTestMixin, View):
    def test_func(self):
        return is_staff_user(self.request.user)
    
    def get(self, request):
        form = CarForm()
        site_info = SiteInfo.objects.first()
        context = {
            'form': form,
            'site_info': site_info
        }
        return render(request, 'add_car.html', context)
    
    def post(self, request):
        form = CarForm(request.POST, request.FILES)
        if form.is_valid():
            car = form.save(commit=False)
            car.created_by = request.user
            car.save()
            messages.success(request, 'Car added successfully!')
            return redirect('car_rental:car_detail', pk=car.pk)
        else:
            messages.error(request, 'Error adding car. Please check the form.')
        
        site_info = SiteInfo.objects.first()
        context = {
            'form': form,
            'site_info': site_info
        }
        return render(request, 'add_car.html', context)

class UpdateCarView(UserPassesTestMixin, UpdateView):
    model = Car
    form_class = CarForm
    template_name = 'update_car.html'
    success_url = reverse_lazy('car_rental:all_cars')
    
    def test_func(self):
        return is_staff_user(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Car updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context

class CustomersView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Customer
    template_name = 'customers.html'
    context_object_name = 'customers'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_queryset(self):
        queryset = Customer.objects.filter(is_deleted=False)
        
        # Search functionality
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter == 'banned':
            queryset = queryset.filter(is_banned=True)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Add statistics
        context['active_customers_count'] = Customer.objects.filter(is_deleted=False, is_banned=False).count()
        context['banned_customers_count'] = Customer.objects.filter(is_deleted=False, is_banned=True).count()
        
        # Calculate total revenue
        total_rental_revenue = Rental.objects.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
        total_purchase_revenue = Purchase.objects.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
        context['total_revenue'] = total_rental_revenue + total_purchase_revenue
        
        return context

class CustomerDetailView(UserPassesTestMixin, DetailView):
    model = Customer
    template_name = 'customer_detail.html'
    context_object_name = 'customer'
    
    def test_func(self):
        return is_staff_user(self.request.user)
    
    def get_queryset(self):
        return Customer.objects.all().select_related('user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Get customer's rentals
        context['rentals'] = Rental.objects.filter(customer=self.object).order_by('-rental_datetime')[:5]
        
        # Get customer's purchases
        context['purchases'] = Purchase.objects.filter(customer=self.object).order_by('-purchase_datetime')[:5]
        
        return context

class CustomerBanDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        action = request.POST.get('action')
        
        if action == 'ban':
            customer.ban()
            messages.success(request, f'Customer {customer.name} has been banned.')
        elif action == 'unban':
            customer.unban()
            messages.success(request, f'Customer {customer.name} has been unbanned.')
        elif action == 'delete':
            customer.delete()
            messages.success(request, f'Customer {customer.name} has been deleted.')
            return redirect('car_rental:customers')
        elif action == 'ban_and_delete':
            customer.ban()
            customer.delete()
            messages.success(request, f'Customer {customer.name} has been banned and deleted.')
            return redirect('car_rental:customers')
        
        return redirect('car_rental:customer_detail', pk=customer.pk)

# --- RENTAL MANAGEMENT VIEWS ---

class RentalDetailView(UserPassesTestMixin, DetailView):
    model = Rental
    template_name = 'rental_detail.html'
    context_object_name = 'rental'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_queryset(self):
        return super().get_queryset().select_related('customer', 'car', 'employee')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Generate WhatsApp URL for pending rentals
        if self.object.status == 'pending':
            customer = self.object.customer
            message = f"Hello, I would like to discuss my rental booking:\n\n"
            message += f"Customer: {customer.name}\n"
            message += f"Phone: {customer.phone}\n"
            message += f"Car: {self.object.car.make} {self.object.car.model} ({self.object.car.year})\n"
            message += f"Rental Dates: {self.object.rental_datetime.strftime('%Y-%m-%d %H:%M')} to {self.object.return_datetime.strftime('%Y-%m-%d %H:%M')}\n"
            message += f"Pickup Location: {self.object.pickup_location}\n\n"
            message += "Please confirm the booking and provide payment instructions."
            
            site_info = SiteInfo.objects.first()
            if site_info and site_info.whatsapp_phone:
                whatsapp_number = ''.join(filter(str.isdigit, site_info.whatsapp_phone))
                context['whatsapp_url'] = f"https://wa.me/{whatsapp_number}?text={quote(message)}"
        
        return context

class ReturnRentalView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Rental
    form_class = RentalReturnForm
    template_name = 'return_rental.html'
    success_url = reverse_lazy('car_rental:my_rentals')  # Fixed this line
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user == self.get_object().customer.user
    
    def form_valid(self, form):
        rental = form.save(commit=False)
        rental.actual_return_datetime = timezone.now()
        rental.status = 'completed'
        rental.save()
        
        # Update car status back to available
        rental.car.status = 'available'
        rental.car.save()
        
        messages.success(self.request, f'Rental for {rental.car.make} {rental.car.model} has been returned successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context

class CustomerRentalView(LoginRequiredMixin, View):
    def get(self, request, car_id):
        car = get_object_or_404(Car, id=car_id, for_rent=True, is_deleted=False)
        
        # Check if car is available for the requested dates
        if not car.is_available(timezone.now(), timezone.now() + timedelta(days=1)):
            messages.error(request, 'This car is not available for the selected dates.')
            return redirect('car_rental:car_detail', pk=car.pk)
        
        # Initialize form with car data
        form = RentalForm(car=car)
        
        context = {
            'car': car,
            'form': form,
            'site_info': SiteInfo.objects.first(),
        }
        return render(request, 'customer_rental.html', context)
    
    def post(self, request, car_id):
        car = get_object_or_404(Car, id=car_id, for_rent=True, is_deleted=False)
        
        form = RentalForm(request.POST, car=car)
        
        if form.is_valid():
            # Create rental with car and customer data
            rental = form.save(commit=False)
            rental.car = car
            
            # Fix: Get the customer through the correct relationship
            try:
                customer = request.user.customer_account
            except Customer.DoesNotExist:
                # If customer doesn't exist, create one
                customer = Customer.objects.create(
                    name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    email=request.user.email,
                    user=request.user
                )
            
            rental.customer = customer
            rental.daily_rate = car.get_rent_price
            rental.status = 'pending'
            rental.payment_status = 'pending'
            
            # Calculate total amount
            rental_days = (rental.return_datetime.date() - rental.rental_datetime.date()).days
            if rental_days < 1:  # Minimum 1 day
                rental_days = 1
            rental.total_amount = rental.daily_rate * rental_days
            
            rental.save()
            
            # Generate WhatsApp URL
            site_info = SiteInfo.objects.first()
            if site_info and site_info.whatsapp_phone:
                phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
                message = quote(
                    f"Hello, I'd like to book a rental for a {car.year} {car.make} {car.model}.\n\n"
                    f"Customer: {customer.name}\n"
                    f"Phone: {customer.phone or 'N/A'}\n"
                    f"Rental Dates: {rental.rental_datetime.strftime('%Y-%m-%d %H:%M')} to {rental.return_datetime.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Pickup Location: {rental.pickup_location or 'N/A'}\n"
                    f"Total Amount: ₦{rental.total_amount}\n\n"
                    f"Please advise on the next steps for payment."
                )
                
                whatsapp_url = f"https://wa.me/{phone}?text={message}"
                
                # Store rental info in session for success page
                request.session['last_rental_id'] = rental.id
                request.session['whatsapp_url'] = whatsapp_url
                
                messages.success(request, 'Your rental booking has been submitted successfully!')
                return redirect('car_rental:whatsapp_rental_success')
            else:
                messages.success(request, 'Your rental booking has been submitted successfully!')
                return redirect('car_rental:home')
        
        context = {
            'car': car,
            'form': form,
            'site_info': SiteInfo.objects.first(),
        }
        return render(request, 'customer_rental.html', context)


class WhatsAppRentalSuccessView(LoginRequiredMixin, View):
    def get(self, request):
        rental_id = request.session.get('last_rental_id')
        whatsapp_url = request.session.get('whatsapp_url')
        
        rental = None
        if rental_id:
            try:
                rental = Rental.objects.get(id=rental_id)
            except Rental.DoesNotExist:
                pass
        
        context = {
            'site_info': SiteInfo.objects.first(),
            'rental': rental,
            'whatsapp_url': whatsapp_url,
        }
        
        return render(request, 'whatsapp_rental_success.html', context)

class UpdateRentalView(UserPassesTestMixin, UpdateView):
    model = Rental
    form_class = StaffRentalForm  # Updated to use StaffRentalForm
    template_name = 'update_rental.html'
    success_url = reverse_lazy('car_rental:rentals')
    
    def test_func(self):
        return is_staff_user(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Rental updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def update_rental_status(request, pk):
    rental = get_object_or_404(Rental, pk=pk)
    
    # Update rental status if provided
    if 'status' in request.POST:
        new_status = request.POST.get('status')
        if new_status in dict(rental.STATUS_CHOICES):
            rental.status = new_status
            rental.save()
            messages.success(request, f'Rental status updated to {rental.get_status_display()}.')
    
    # Update payment status if provided
    if 'payment_status' in request.POST:
        new_payment_status = request.POST.get('payment_status')
        if new_payment_status in dict(rental.PAYMENT_STATUS_CHOICES):
            rental.payment_status = new_payment_status
            rental.save()
            messages.success(request, f'Payment status updated to {rental.get_payment_status_display()}.')
    
    return redirect('car_rental:rental_detail', pk=rental.pk)

# --- PURCHASE MANAGEMENT VIEWS ---

class CreatePurchaseView(UserPassesTestMixin, CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = 'create_purchase.html'
    success_url = reverse_lazy('car_rental:purchases')
    
    def test_func(self):
        return is_staff_user(self.request.user)
    
    def form_valid(self, form):
        purchase = form.save(commit=False)
        purchase.employee = self.request.user
        purchase.save()
        send_purchase_confirmation_email(purchase)
        messages.success(self.request, 'Purchase created successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context


class CustomerPurchaseView(LoginRequiredMixin, View):
    def get(self, request, car_id):
        car = get_object_or_404(Car, id=car_id, for_sale=True, is_deleted=False)
        
        # Initialize form with car data
        form = PurchaseForm(request=request)
        
        context = {
            'car': car,
            'form': form,
            'site_info': SiteInfo.objects.first(),
        }
        return render(request, 'customer_purchase.html', context)
    
    def post(self, request, car_id):
        car = get_object_or_404(Car, id=car_id, for_sale=True, is_deleted=False)
        
        form = PurchaseForm(request.POST, request=request)
        
        if form.is_valid():
            # Create purchase with car and customer data
            purchase = form.save(commit=False)
            purchase.car = car
            purchase.customer = request.user.customer_account
            purchase.save()
            
            # Generate WhatsApp URL with customer information
            site_info = SiteInfo.objects.first()
            if site_info and site_info.whatsapp_phone:
                phone = site_info.whatsapp_phone.replace('+', '').replace(' ', '').replace('-', '')
                
                # Get customer information
                customer = request.user.customer_account
                customer_name = customer.name
                customer_email = customer.email
                customer_phone = customer.phone
                
                # Format delivery date if available
                delivery_date = ""
                if purchase.delivery_datetime:
                    delivery_date = purchase.delivery_datetime.strftime('%B %d, %Y')
                
                message = quote(
                    f"Hello, I'd like to complete my purchase for a {car.year} {car.make} {car.model}.\n\n"
                    f"Customer Information:\n"
                    f"Name: {customer_name}\n"
                    f"Email: {customer_email}\n"
                    f"Phone: {customer_phone}\n\n"
                    f"Purchase Details:\n"
                    f"Purchase ID: {purchase.id}\n"
                    f"Car: {car.year} {car.make} {car.model}\n"
                    f"VIN: {car.vin or 'N/A'}\n"
                    f"Total Amount: ₦{purchase.total_amount}\n"
                    f"Delivery Date: {delivery_date or 'To be determined'}\n"
                    f"Delivery Address: {purchase.delivery_address or 'To be provided'}\n\n"
                    f"Please advise on the next steps for payment."
                )
                
                whatsapp_url = f"https://wa.me/{phone}?text={message}"
                
                # Store purchase info in session for success page
                request.session['last_purchase_id'] = purchase.id
                request.session['whatsapp_url'] = whatsapp_url
                
                messages.success(request, 'Your purchase request has been submitted successfully!')
                return redirect('car_rental:whatsapp_purchase_success')
            else:
                messages.success(request, 'Your purchase request has been submitted successfully!')
                return redirect('car_rental:purchase_success')
        
        context = {
            'car': car,
            'form': form,
            'site_info': SiteInfo.objects.first(),
        }
        return render(request, 'customer_purchase.html', context)

class PurchaseDetailView(DetailView):
    model = Purchase
    template_name = 'purchase_detail.html'
    context_object_name = 'purchase'
    
    def get_queryset(self):
        # Allow customers to see their own purchases, and superusers to see all purchases
        if self.request.user.is_superuser:
            return Purchase.objects.all().select_related('customer', 'car', 'employee')
        else:
            try:
                customer = self.request.user.customer_account
                return Purchase.objects.filter(customer=customer).select_related('car', 'employee')
            except (Customer.DoesNotExist, AttributeError):
                return Purchase.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Add a flag to indicate if the current user can edit this purchase
        context['can_edit'] = self.request.user.is_superuser
        
        return context

class UpdatePurchaseView(UserPassesTestMixin, UpdateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = 'update_purchase.html'
    
    def test_func(self):
        # Only allow superusers to update purchases
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        # Redirect to login or show 403 for non-superusers
        if self.request.user.is_authenticated:
            # User is logged in but not a superuser
            return redirect('car_rental:home')  # or show a 403 page
        else:
            # User is not logged in
            return redirect('car_rental:login')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Purchase updated successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_success_url(self):
        # Redirect to the purchase detail page after updating
        return reverse('car_rental:purchase_detail', kwargs={'pk': self.object.pk})

@require_POST
@login_required
@user_passes_test(is_staff_user)
def update_purchase_status(request, purchase_id):
    purchase = get_object_or_404(Purchase, pk=purchase_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Purchase.STATUS_CHOICES):
        purchase.status = new_status
        purchase.save()
        messages.success(request, f'Purchase status updated to {new_status}.')
    else:
        messages.error(request, 'Invalid status.')
    
    return redirect('car_rental:purchase_detail', pk=purchase.pk)

class PurchaseSuccessView(TemplateView):
    template_name = 'purchase_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Get last purchase from session
        purchase_id = self.request.session.get('last_purchase_id')
        if purchase_id:
            try:
                context['purchase'] = Purchase.objects.get(id=purchase_id)
            except Purchase.DoesNotExist:
                pass
        
        return context

class WhatsAppPurchaseSuccessView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        purchase_id = request.session.get('last_purchase_id')
        whatsapp_url = request.session.get('whatsapp_url')
        
        purchase = None
        if purchase_id:
            try:
                purchase = Purchase.objects.get(id=purchase_id)
            except Purchase.DoesNotExist:
                pass
        
        context = {
            'site_info': site_info,
            'purchase': purchase,
            'whatsapp_url': whatsapp_url,
        }
        
        return render(request, 'whatsapp_purchase_success.html', context)

@require_POST
@login_required
@user_passes_test(is_staff_user)
def update_purchase_status(request, purchase_id):
    purchase = get_object_or_404(Purchase, pk=purchase_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Purchase.STATUS_CHOICES):
        purchase.status = new_status
        purchase.save()
        messages.success(request, f'Purchase status updated to {new_status}.')
    else:
        messages.error(request, 'Invalid status.')
    
    return redirect('car_rental:purchase_detail', pk=purchase.pk)

from django.contrib.contenttypes.models import ContentType
#Rating views
class SubmitRentalRatingView(LoginRequiredMixin, CreateView):
    model = CustomerRating
    form_class = CustomerRatingForm
    template_name = 'submit_rating.html'
    success_url = reverse_lazy('car_rental:my_rentals')
    
    def dispatch(self, request, *args, **kwargs):
        rental_id = kwargs.get('rental_id')
        try:
            rental = Rental.objects.get(id=rental_id, customer__user=request.user)
            if rental.status != 'completed':
                messages.error(request, "You can only rate completed rentals.")
                return redirect('car_rental:my_rentals')
            if CustomerRating.objects.filter(
                customer=rental.customer,
                content_type=ContentType.objects.get_for_model(Rental),
                object_id=rental.id
            ).exists():
                messages.error(request, "You have already rated this rental.")
                return redirect('car_rental:my_rentals')
        except Rental.DoesNotExist:
            messages.error(request, "Rental not found.")
            return redirect('car_rental:my_rentals')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        rental_id = self.kwargs.get('rental_id')
        rental = Rental.objects.get(id=rental_id)
        form.instance.customer = rental.customer
        form.instance.service_type = 'rental'
        form.instance.content_type = ContentType.objects.get_for_model(Rental)
        form.instance.object_id = rental.id
        messages.success(self.request, "Thank you for your rating!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rental_id = self.kwargs.get('rental_id')
        context['rental'] = Rental.objects.get(id=rental_id)
        context['site_info'] = SiteInfo.objects.first()
        context['item_type'] = 'Rental'
        context['item_title'] = f"{context['rental'].car.make} {context['rental'].car.model}"
        return context

class SubmitPurchaseRatingView(LoginRequiredMixin, CreateView):
    model = CustomerRating
    form_class = CustomerRatingForm
    template_name = 'submit_rating.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        purchase_id = self.kwargs.get('purchase_id')
        if purchase_id:
            context['purchase'] = get_object_or_404(Purchase, pk=purchase_id)
        
        return context
    
    def form_valid(self, form):
        purchase_id = self.kwargs.get('purchase_id')
        purchase = get_object_or_404(Purchase, pk=purchase_id)
        
        # Check if user is the customer who made the purchase
        if purchase.customer != self.request.user.customer_account:
            messages.error(self.request, "You can only rate your own purchases.")
            return redirect('car_rental:my_purchases')
        
        # Check if purchase is delivered
        if purchase.status != 'delivered':
            messages.error(self.request, "You can only rate delivered purchases.")
            return redirect('car_rental:my_purchases')
        
        # Check if already rated
        if CustomerRating.objects.filter(
            customer=self.request.user.customer_account,
            content_type=ContentType.objects.get_for_model(Purchase),
            object_id=purchase.id
        ).exists():
            messages.error(self.request, "You have already rated this purchase.")
            return redirect('car_rental:my_purchases')
        
        # Set the rating fields
        form.instance.customer = self.request.user.customer_account
        form.instance.service_type = 'purchase'
        form.instance.content_type = ContentType.objects.get_for_model(Purchase)
        form.instance.object_id = purchase.id
        
        rating = form.save()
        messages.success(self.request, "Thank you for rating your purchase experience!")
        
        return redirect('car_rental:my_purchases')

class SubmitServiceRatingView(LoginRequiredMixin, CreateView):
    model = CustomerRating
    form_class = CustomerRatingForm
    template_name = 'submit_rating.html'
    success_url = reverse_lazy('car_rental:my_services')
    
    def dispatch(self, request, *args, **kwargs):
        service_id = kwargs.get('service_id')
        try:
            service_booking = ServiceBooking.objects.get(id=service_id, customer__user=request.user)
            if service_booking.status != 'completed':
                messages.error(request, "You can only rate completed services.")
                return redirect('car_rental:my_services')
            if CustomerRating.objects.filter(
                customer=service_booking.customer,
                content_type=ContentType.objects.get_for_model(ServiceBooking),
                object_id=service_booking.id
            ).exists():
                messages.error(request, "You have already rated this service.")
                return redirect('car_rental:my_services')
        except ServiceBooking.DoesNotExist:
            messages.error(request, "Service booking not found.")
            return redirect('car_rental:my_services')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        service_id = self.kwargs.get('service_id')
        service_booking = ServiceBooking.objects.get(id=service_id)
        form.instance.customer = service_booking.customer
        form.instance.service_type = 'service'
        form.instance.content_type = ContentType.objects.get_for_model(ServiceBooking)
        form.instance.object_id = service_booking.id
        messages.success(self.request, "Thank you for your rating!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_id = self.kwargs.get('service_id')
        context['service'] = ServiceBooking.objects.get(id=service_id)
        context['site_info'] = SiteInfo.objects.first()
        context['item_type'] = 'Service'
        context['item_title'] = f"{context['service'].get_service_type_display()}"
        return context

class MyServicesView(LoginRequiredMixin, ListView):
    model = ServiceBooking
    template_name = 'my_services.html'
    context_object_name = 'bookings'
    paginate_by = 10
    
    def get_queryset(self):
        try:
            customer = self.request.user.customer_account
            return ServiceBooking.objects.filter(customer=customer).order_by('-created_at')
        except (Customer.DoesNotExist, AttributeError):
            return ServiceBooking.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = SiteInfo.objects.first()
        
        # Get the full queryset for statistics calculation
        try:
            customer = self.request.user.customer_account
            # Create a new queryset for statistics to avoid slicing issues
            full_bookings = ServiceBooking.objects.filter(customer=customer)
            
            # Calculate stats
            context['total_bookings'] = full_bookings.count()
            context['pending_bookings'] = full_bookings.filter(status='pending').count()
            context['completed_bookings'] = full_bookings.filter(status='completed').count()
                
        except (Customer.DoesNotExist, AttributeError):
            context['total_bookings'] = 0
            context['pending_bookings'] = 0
            context['completed_bookings'] = 0
                
        return context

    
class ServicesOverviewView(View):
    def get(self, request):
        site_info = SiteInfo.objects.first()
        context = {'site_info': site_info}
        return render(request, 'services_overview.html', context)
    
#report view
class ReportsDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for viewing reports and analytics"""
    template_name = 'reports_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Only allow staff and managers to view reports
        if not (self.request.user.is_staff or self.request.user.profile.role in ['manager', 'admin']):
            context['error'] = "You don't have permission to view reports."
            return context
        
        # Get current date and date ranges
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timezone.timedelta(days=1)).replace(day=1)
        last_month_end = this_month_start - timezone.timedelta(days=1)
        
        # Calculate rental statistics
        rentals_this_month = Rental.objects.filter(
            rental_datetime__date__gte=this_month_start,
            rental_datetime__date__lte=today
        )
        
        rentals_last_month = Rental.objects.filter(
            rental_datetime__date__gte=last_month_start,
            rental_datetime__date__lte=last_month_end
        )
        
        # Calculate purchase statistics
        purchases_this_month = Purchase.objects.filter(
            purchase_datetime__date__gte=this_month_start,
            purchase_datetime__date__lte=today
        )
        
        purchases_last_month = Purchase.objects.filter(
            purchase_datetime__date__gte=last_month_start,
            purchase_datetime__date__lte=last_month_end
        )
        
        # Calculate service booking statistics
        service_bookings_this_month = ServiceBooking.objects.filter(
            created_at__date__gte=this_month_start,
            created_at__date__lte=today
        )
        
        service_bookings_last_month = ServiceBooking.objects.filter(
            created_at__date__gte=last_month_start,
            created_at__date__lte=last_month_end
        )
        
        # Calculate revenue
        rental_revenue_this_month = rentals_this_month.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        rental_revenue_last_month = rentals_last_month.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        purchase_revenue_this_month = purchases_this_month.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        purchase_revenue_last_month = purchases_last_month.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Calculate service revenue (assuming service bookings have a price field)
        service_revenue_this_month = service_bookings_this_month.filter(
            status='completed'
        ).count() * 5000  # Example: average service price
        
        service_revenue_last_month = service_bookings_last_month.filter(
            status='completed'
        ).count() * 5000
        
        # Calculate growth percentages
        rental_count_growth = 0
        if rentals_last_month.count() > 0:
            rental_count_growth = ((rentals_this_month.count() - rentals_last_month.count()) / rentals_last_month.count()) * 100
        
        purchase_count_growth = 0
        if purchases_last_month.count() > 0:
            purchase_count_growth = ((purchases_this_month.count() - purchases_last_month.count()) / purchases_last_month.count()) * 100
        
        service_booking_growth = 0
        if service_bookings_last_month.count() > 0:
            service_booking_growth = ((service_bookings_this_month.count() - service_bookings_last_month.count()) / service_bookings_last_month.count()) * 100
        
        rental_revenue_growth = 0
        if rental_revenue_last_month > 0:
            rental_revenue_growth = ((rental_revenue_this_month - rental_revenue_last_month) / rental_revenue_last_month) * 100
        
        purchase_revenue_growth = 0
        if purchase_revenue_last_month > 0:
            purchase_revenue_growth = ((purchase_revenue_this_month - purchase_revenue_last_month) / purchase_revenue_last_month) * 100
        
        service_revenue_growth = 0
        if service_revenue_last_month > 0:
            service_revenue_growth = ((service_revenue_this_month - service_revenue_last_month) / service_revenue_last_month) * 100
        
        total_revenue_this_month = rental_revenue_this_month + purchase_revenue_this_month + service_revenue_this_month
        total_revenue_last_month = rental_revenue_last_month + purchase_revenue_last_month + service_revenue_last_month
        
        total_revenue_growth = 0
        if total_revenue_last_month > 0:
            total_revenue_growth = ((total_revenue_this_month - total_revenue_last_month) / total_revenue_last_month) * 100
        
        # Get top cars by rental count with revenue
        top_rented_cars = Car.objects.filter(
            rentals__rental_datetime__date__gte=this_month_start,
            rentals__rental_datetime__date__lte=today
        ).annotate(
            rental_count=Count('rentals'),
            rental_revenue=Sum('rentals__total_amount')
        ).order_by('-rental_count')[:5]
        
        # Get top cars by purchase count with revenue
        top_purchased_cars = Car.objects.filter(
            purchases__purchase_datetime__date__gte=this_month_start,
            purchases__purchase_datetime__date__lte=today
        ).annotate(
            purchase_count=Count('purchases'),
            purchase_revenue=Sum('purchases__total_amount')
        ).order_by('-purchase_count')[:5]
        
        # Get service bookings by type
        diagnostic_count_this_month = service_bookings_this_month.filter(service_type='diagnostic').count()
        repair_count_this_month = service_bookings_this_month.filter(service_type='repair').count()
        upgrade_count_this_month = service_bookings_this_month.filter(service_type='upgrade').count()
        consultation_count_this_month = service_bookings_this_month.filter(service_type='consultation').count()
        
        diagnostic_count_last_month = service_bookings_last_month.filter(service_type='diagnostic').count()
        repair_count_last_month = service_bookings_last_month.filter(service_type='repair').count()
        upgrade_count_last_month = service_bookings_last_month.filter(service_type='upgrade').count()
        consultation_count_last_month = service_bookings_last_month.filter(service_type='consultation').count()
        
        # Get service status counts
        pending_services_count = service_bookings_this_month.filter(status='pending').count()
        confirmed_services_count = service_bookings_this_month.filter(status='confirmed').count()
        in_progress_services_count = service_bookings_this_month.filter(status='in_progress').count()
        completed_services_count = service_bookings_this_month.filter(status='completed').count()
        cancelled_services_count = service_bookings_this_month.filter(status='cancelled').count()
        
        # Get recent activities
        recent_activities = []
        
        # Recent rentals
        for rental in Rental.objects.filter(rental_datetime__date__gte=this_month_start).order_by('-rental_datetime')[:5]:
            recent_activities.append({
                'date': rental.rental_datetime,
                'type': 'rental',
                'customer_name': rental.customer.name,
                'item_name': f"{rental.car.make} {rental.car.model} ({rental.car.year})",
                'amount': rental.total_amount,
                'status': rental.status
            })
        
        # Recent purchases
        for purchase in Purchase.objects.filter(purchase_datetime__date__gte=this_month_start).order_by('-purchase_datetime')[:5]:
            recent_activities.append({
                'date': purchase.purchase_datetime,
                'type': 'purchase',
                'customer_name': purchase.customer.name,
                'item_name': f"{purchase.car.make} {purchase.car.model} ({purchase.car.year})",
                'amount': purchase.total_amount,
                'status': purchase.status
            })
        
        # Recent service bookings
        for booking in ServiceBooking.objects.filter(created_at__date__gte=this_month_start).order_by('-created_at')[:5]:
            recent_activities.append({
                'date': booking.created_at,
                'type': 'service',
                'customer_name': booking.name,
                'item_name': f"{booking.get_service_type_display()} - {booking.car_make} {booking.car_model}",
                'amount': None,  # Service bookings may not have a fixed price
                'status': booking.status
            })
        
        # Sort activities by date
        recent_activities.sort(key=lambda x: x['date'], reverse=True)
        recent_activities = recent_activities[:10]  # Keep only the 10 most recent
        
        context.update({
            'site_info': SiteInfo.objects.first(),
            'rentals_this_month': rentals_this_month,
            'rentals_last_month': rentals_last_month,
            'purchases_this_month': purchases_this_month,
            'purchases_last_month': purchases_last_month,
            'service_bookings_this_month': service_bookings_this_month,
            'service_bookings_last_month': service_bookings_last_month,
            'rental_revenue_this_month': rental_revenue_this_month,
            'rental_revenue_last_month': rental_revenue_last_month,
            'purchase_revenue_this_month': purchase_revenue_this_month,
            'purchase_revenue_last_month': purchase_revenue_last_month,
            'service_revenue_this_month': service_revenue_this_month,
            'service_revenue_last_month': service_revenue_last_month,
            'total_revenue_this_month': total_revenue_this_month,
            'total_revenue_last_month': total_revenue_last_month,
            'rental_count_growth': rental_count_growth,
            'purchase_count_growth': purchase_count_growth,
            'service_booking_growth': service_booking_growth,
            'rental_revenue_growth': rental_revenue_growth,
            'purchase_revenue_growth': purchase_revenue_growth,
            'service_revenue_growth': service_revenue_growth,
            'total_revenue_growth': total_revenue_growth,
            'top_rented_cars': top_rented_cars,
            'top_purchased_cars': top_purchased_cars,
            'diagnostic_count_this_month': diagnostic_count_this_month,
            'repair_count_this_month': repair_count_this_month,
            'upgrade_count_this_month': upgrade_count_this_month,
            'consultation_count_this_month': consultation_count_this_month,
            'diagnostic_count_last_month': diagnostic_count_last_month,
            'repair_count_last_month': repair_count_last_month,
            'upgrade_count_last_month': upgrade_count_last_month,
            'consultation_count_last_month': consultation_count_last_month,
            'pending_services_count': pending_services_count,
            'confirmed_services_count': confirmed_services_count,
            'in_progress_services_count': in_progress_services_count,
            'completed_services_count': completed_services_count,
            'cancelled_services_count': cancelled_services_count,
            'recent_activities': recent_activities,
        })
        
        return context

# API Views
class CarAvailabilityAPIView(LoginRequiredMixin, View):
    """API endpoint to check car availability"""
    def get(self, request):
        car_id = request.GET.get('car_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not all([car_id, start_date, end_date]):
            return JsonResponse({'error': 'Missing required parameters'}, status=400)
        
        try:
            car = Car.objects.get(id=car_id)
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            
            is_available = car.is_available(start_date, end_date)
            
            return JsonResponse({
                'car_id': car_id,
                'available': is_available,
                'message': 'Car is available' if is_available else 'Car is not available for the selected dates'
            })
        except Car.DoesNotExist:
            return JsonResponse({'error': 'Car not found'}, status=404)
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)


class ServiceDatesAPIView(View):
    def get(self, request):
        # Simple implementation
        return JsonResponse({'dates': []})

class TechnicianScheduleAPIView(View):
    def get(self, request):
        # Simple implementation
        return JsonResponse({'schedule': []})

#policy
def privacy_policy(request):
    site_info = SiteInfo.objects.first()
    context = {
        'site_info': site_info
    }
    return render(request, 'privacy_policy.html', context)

def terms_of_service(request):
    site_info = SiteInfo.objects.first()
    context = {
        'site_info': site_info
    }
    return render(request, 'terms_of_service.html', context)

#marksent view
@require_POST
@login_required
def mark_whatsapp_sent(request, pk):
    """Mark a service booking as WhatsApp message sent"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        booking = ServiceBooking.objects.get(pk=pk)
        booking.whatsapp_sent = True
        booking.save()
        
        return JsonResponse({
            'success': True,
            'message': 'WhatsApp message marked as sent'
        })
    except ServiceBooking.DoesNotExist:
        return JsonResponse({'error': 'Service booking not found'}, status=404)

# --- ERROR HANDLING VIEWS ---
def permission_denied(request, exception=None):
    site_info = SiteInfo.objects.first()
    context = {'site_info': site_info}
    return render(request, '403.html', context, status=403)

def page_not_found(request, exception=None):
    site_info = SiteInfo.objects.first()
    context = {'site_info': site_info}
    return render(request, '404.html', context, status=404)

def server_error(request):
    site_info = SiteInfo.objects.first()
    context = {'site_info': site_info}
    return render(request, '500.html', context, status=500)

def handle_no_permission(self):
    # Show 403 page for non-superusers
    from django.shortcuts import render
    return render(self.request, '403.html', status=403)

@login_required
def logout_view(request):
    """Log out the user and redirect to home page"""
    logout(request)
    messages.info(request, 'You have been successfully logged out.')
    return redirect('car_rental:home')
