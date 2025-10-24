from django.urls import path, reverse_lazy
from django.views.generic import TemplateView
from . import views

app_name = 'car_rental'

urlpatterns = [
    # Public facing views
    path('', views.HomeView.as_view(), name='home'),
    path('all-cars/', views.CarListView.as_view(), name='all_cars'),
    path('rent-cars/', views.RentCarListView.as_view(), name='rent_cars'),
    path('sale-cars/', views.SaleCarListView.as_view(), name='sale_cars'),
    path('car/<int:pk>/', views.CarDetailView.as_view(), name='car_detail'),
    path('car/<slug:slug>/', views.CarDetailView.as_view(), name='car_detail_slug'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    
    # Individual service booking views
    path('book-diagnostic/', views.BookDiagnosticServiceView.as_view(), name='book_diagnostic'),
    path('book-repair/', views.BookRepairServiceView.as_view(), name='book_repair'),
    path('book-upgrade/', views.BookUpgradeServiceView.as_view(), name='book_upgrade'),
    path('book-consultation/', views.BookConsultationServiceView.as_view(), name='book_consultation'),

    #service overview
    path('services/', views.ServicesOverviewView.as_view(), name='services_overview'),

    # Service booking management
    path('service-bookings/', views.ServiceBookingListView.as_view(), name='service_booking_list'),
    path('service-bookings/<int:pk>/', views.ServiceBookingDetailView.as_view(), name='service_booking_detail'),
    path('service-bookings/<int:pk>/update/', views.ServiceBookingUpdateView.as_view(), name='service_booking_update'),
    path('service-bookings/<int:pk>/update-status/', views.update_service_booking_status, name='update_service_booking_status'),
    
    # WhatsApp success page
    path('whatsapp-success/', views.WhatsAppSuccessView.as_view(), name='whatsapp_success'),
    
    # Authentication views
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # User profile views
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('change-password/', views.change_password, name='change_password'),
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # User service history
    path('my-rentals/', views.MyRentalsView.as_view(), name='my_rentals'),
    path('my-purchases/', views.MyPurchasesView.as_view(), name='my_purchases'),
    
    # Staff/Admin views
    path('add-car/', views.AddCarView.as_view(), name='add_car'),
    path('car/<int:pk>/update/', views.UpdateCarView.as_view(), name='update_car'),
    path('customers/', views.CustomersView.as_view(), name='customers'),
    path('site-info/edit/', views.site_info_edit, name='site_info_edit'),
    path('purchase/<int:purchase_id>/update-status/', views.update_purchase_status, name='update_purchase_status'),
    path('customer/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customer/<int:pk>/ban-delete/', views.CustomerBanDeleteView.as_view(), name='customer_ban_delete'),
    
    # Admin/staff purchase list
    path('purchases/', views.PurchasesListView.as_view(), name='purchases'),
    
    # Rental management
    path('rentals/<int:pk>/', views.RentalDetailView.as_view(), name='rental_detail'),
    path('rentals/<int:pk>/return/', views.ReturnRentalView.as_view(), name='return_rental'),
    path('rentals/book/<int:car_id>/', views.CustomerRentalView.as_view(), name='customer_rental'),
    path('rentals/<int:pk>/update/', views.UpdateRentalView.as_view(), name='update_rental'),
    path('rentals/<int:pk>/update-status/', views.update_rental_status, name='update_rental_status'),
    path('rentals/whatsapp-success/', views.WhatsAppRentalSuccessView.as_view(), name='whatsapp_rental_success'),
    
    # Purchase management
    path('purchases/create-staff/', views.CreatePurchaseView.as_view(), name='create_purchase'), 
    path('purchases/finalize/<int:car_id>/', views.CustomerPurchaseView.as_view(), name='customer_purchase'),  
    path('purchases/<int:pk>/', views.PurchaseDetailView.as_view(), name='purchase_detail'),
    path('purchases/<int:pk>/update/', views.UpdatePurchaseView.as_view(), name='update_purchase'),
    path('purchase/success/', views.PurchaseSuccessView.as_view(), name='purchase_success'),
    path('whatsapp-purchase-success/', views.WhatsAppPurchaseSuccessView.as_view(), name='whatsapp_purchase_success'),
    
    # Rating URLs
    path('rate/rental/<int:rental_id>/', views.SubmitRentalRatingView.as_view(), name='submit_rental_rating'),
    path('rate/purchase/<int:purchase_id>/', views.SubmitPurchaseRatingView.as_view(), name='submit_purchase_rating'),
    path('rate/service/<int:service_id>/', views.SubmitServiceRatingView.as_view(), name='submit_service_rating'),

    # My Services URL
    path('my-services/', views.MyServicesView.as_view(), name='my_services'),
    
    # Reports and analytics
    path('reports/', views.ReportsDashboardView.as_view(), name='reports_dashboard'),
    
    # API endpoints for AJAX requests
    path('api/car-availability/', views.CarAvailabilityAPIView.as_view(), name='api_car_availability'),
    
    # policy
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    # Error pages
    path('403/', views.permission_denied, name='permission_denied'),
    path('404/', views.page_not_found, name='page_not_found'),
    path('500/', views.server_error, name='server_error'),
    #mark sent
    path('service-bookings/<int:pk>/mark-whatsapp-sent/', views.mark_whatsapp_sent, name='mark_whatsapp_sent'),
    # services success
    path('whatsapp-diagnostic-success/', views.WhatsAppDiagnosticSuccessView.as_view(), name='whatsapp_diagnostic_success'),
    path('whatsapp-repair-success/', views.WhatsAppRepairSuccessView.as_view(), name='whatsapp_repair_success'),
    path('whatsapp-upgrade-success/', views.WhatsAppUpgradeSuccessView.as_view(), name='whatsapp_upgrade_success'),
    path('whatsapp-consultation-success/', views.WhatsAppConsultationSuccessView.as_view(), name='whatsapp_consultation_success'),
]