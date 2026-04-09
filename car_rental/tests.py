from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Car, Customer, Rental, Purchase, SiteInfo, UserProfile, DiagnosticService, RepairService, UpgradeService, ConsultationService
from .forms import CarForm, RentalForm, PurchaseForm
from .utils import calculate_distance, format_currency, generate_invoice_number

User = get_user_model()

class CarModelTests(TestCase):
    def setUp(self):
        self.car_data = {
            'make': 'Toyota',
            'model': 'Camry',
            'year': 2022,
            'default_price': 50.00,
            'description': 'A reliable sedan',
            'for_rent': True,
            'rent_price': 60.00,
            'status': 'available'
        }
    
    def test_car_creation(self):
        car = Car.objects.create(**self.car_data)
        self.assertEqual(car.make, 'Toyota')
        self.assertEqual(car.model, 'Camry')
        self.assertEqual(car.year, 2022)
        self.assertEqual(car.default_price, 50.00)
        self.assertTrue(car.for_rent)
        self.assertEqual(car.rent_price, 60.00)
        self.assertEqual(car.status, 'available')
    
    def test_car_str_representation(self):
        car = Car.objects.create(**self.car_data)
        self.assertEqual(str(car), '2022 Toyota Camry')
    
    def test_get_rent_price(self):
        car = Car.objects.create(**self.car_data)
        self.assertEqual(car.get_rent_price, 60.00)
        
        # Test with no rent_price
        car.rent_price = None
        car.save()
        self.assertEqual(car.get_rent_price, 50.00)
    
    def test_get_sale_price(self):
        car_data = self.car_data.copy()
        car_data.update({
            'for_rent': False,
            'for_sale': True,
            'sale_price': 25000.00
        })
        car = Car.objects.create(**car_data)
        self.assertEqual(car.get_sale_price, 25000.00)
        
        # Test with no sale_price
        car.sale_price = None
        car.save()
        self.assertEqual(car.get_sale_price, 50.00)
    
    def test_car_availability(self):
        car = Car.objects.create(**self.car_data)
        
        # Car should be available initially
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=5)
        self.assertTrue(car.is_available(start_date, end_date))
        
        # Create a rental that overlaps with the dates
        customer = Customer.objects.create(name='John Doe', email='john@example.com')
        Rental.objects.create(
            customer=customer,
            car=car,
            rental_datetime=timezone.now(),
            return_datetime=timezone.now() + timedelta(days=3),
            daily_rate=60.00,
            status='active'
        )
        
        # Car should not be available for overlapping dates
        self.assertFalse(car.is_available(start_date, end_date))
        
        # Car should be available for non-overlapping dates
        future_start = end_date + timedelta(days=1)
        future_end = future_start + timedelta(days=5)
        self.assertTrue(car.is_available(future_start, future_end))

class RentalModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
    
    def test_rental_creation(self):
        rental = Rental.objects.create(
            customer=self.customer,
            car=self.car,
            rental_datetime=timezone.now(),
            return_datetime=timezone.now() + timedelta(days=3),
            daily_rate=60.00,
            status='active'
        )
        self.assertEqual(rental.customer, self.customer)
        self.assertEqual(rental.car, self.car)
        self.assertEqual(rental.daily_rate, 60.00)
        self.assertEqual(rental.status, 'active')
    
    def test_rental_str_representation(self):
        rental = Rental.objects.create(
            customer=self.customer,
            car=self.car,
            rental_datetime=timezone.now(),
            return_datetime=timezone.now() + timedelta(days=3),
            daily_rate=60.00,
            status='active'
        )
        self.assertEqual(str(rental), 'John Doe - Toyota Camry')
    
    def test_rental_days_calculation(self):
        rental_datetime = timezone.now()
        return_datetime = rental_datetime + timedelta(days=3)
        
        rental = Rental.objects.create(
            customer=self.customer,
            car=self.car,
            rental_datetime=rental_datetime,
            return_datetime=return_datetime,
            daily_rate=60.00,
            status='active'
        )
        
        self.assertEqual(rental.rental_days, 3)
    
    def test_late_fee_calculation(self):
        rental_datetime = timezone.now()
        return_datetime = rental_datetime + timedelta(days=3)
        
        rental = Rental.objects.create(
            customer=self.customer,
            car=self.car,
            rental_datetime=rental_datetime,
            return_datetime=return_datetime,
            daily_rate=60.00,
            status='active'
        )
        
        # No late fee initially
        self.assertEqual(rental.late_fee, 0)
        
        # Simulate late return (2 hours late)
        rental.actual_return_datetime = return_datetime + timedelta(hours=2)
        rental.save()
        
        # Should have a late fee of $20 (2 hours * $10 per hour)
        self.assertEqual(rental.late_fee, 20)
    
    def test_total_amount_due_calculation(self):
        rental_datetime = timezone.now()
        return_datetime = rental_datetime + timedelta(days=3)
        
        rental = Rental.objects.create(
            customer=self.customer,
            car=self.car,
            rental_datetime=rental_datetime,
            return_datetime=return_datetime,
            daily_rate=60.00,
            total_amount=180.00,
            status='active'
        )
        
        # No late fee initially
        self.assertEqual(rental.total_amount_due, 180.00)
        
        # Simulate late return (2 hours late)
        rental.actual_return_datetime = return_datetime + timedelta(hours=2)
        rental.save()
        
        # Should include late fee
        self.assertEqual(rental.total_amount_due, 200.00)

class PurchaseModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=25000.00,
            description='A reliable sedan',
            for_sale=True,
            sale_price=28000.00,
            status='available'
        )
    
    def test_purchase_creation(self):
        purchase = Purchase.objects.create(
            customer=self.customer,
            car=self.car,
            purchase_datetime=timezone.now(),
            purchase_price=28000.00,
            status='pending'
        )
        self.assertEqual(purchase.customer, self.customer)
        self.assertEqual(purchase.car, self.car)
        self.assertEqual(purchase.purchase_price, 28000.00)
        self.assertEqual(purchase.status, 'pending')
    
    def test_purchase_str_representation(self):
        purchase = Purchase.objects.create(
            customer=self.customer,
            car=self.car,
            purchase_datetime=timezone.now(),
            purchase_price=28000.00,
            status='pending'
        )
        self.assertEqual(str(purchase), 'John Doe - Toyota Camry')
    
    def test_net_amount_calculation(self):
        purchase = Purchase.objects.create(
            customer=self.customer,
            car=self.car,
            purchase_datetime=timezone.now(),
            purchase_price=28000.00,
            taxes=2000.00,
            fees=500.00,
            status='pending'
        )
        
        # No trade-in initially
        self.assertEqual(purchase.net_amount, 30500.00)
        
        # Add trade-in
        trade_in_car = Car.objects.create(
            make='Honda',
            model='Civic',
            year=2018,
            default_price=15000.00,
            description='A compact car',
            for_sale=True,
            sale_price=17000.00,
            status='available'
        )
        
        purchase.trade_in = trade_in_car
        purchase.trade_in_value = 12000.00
        purchase.save()
        
        # Net amount should be reduced by trade-in value
        self.assertEqual(purchase.net_amount, 18500.00)

class DiagnosticServiceModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
    
    def test_diagnostic_service_creation(self):
        service = DiagnosticService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Engine Diagnostic',
            description='Check engine performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            cost=100.00,
            status='scheduled'
        )
        self.assertEqual(service.customer, self.customer)
        self.assertEqual(service.car, self.car)
        self.assertEqual(service.title, 'Engine Diagnostic')
        self.assertEqual(service.status, 'scheduled')
    
    def test_diagnostic_service_str_representation(self):
        service = DiagnosticService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Engine Diagnostic',
            description='Check engine performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            cost=100.00,
            status='scheduled'
        )
        self.assertEqual(str(service), 'Engine Diagnostic - Toyota Camry')
    
    def test_car_status_update_on_service_creation(self):
        # Car should be available initially
        self.assertEqual(self.car.status, 'available')
        
        # Create a diagnostic service
        service = DiagnosticService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Engine Diagnostic',
            description='Check engine performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            cost=100.00,
            status='scheduled'
        )
        
        # Car status should be updated to 'in_service'
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, 'in_service')
    
    def test_car_status_update_on_service_completion(self):
        # Create a diagnostic service
        service = DiagnosticService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Engine Diagnostic',
            description='Check engine performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            cost=100.00,
            status='scheduled'
        )
        
        # Car status should be 'in_service'
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, 'in_service')
        
        # Complete the service
        service.status = 'completed'
        service.completed_date = timezone.now()
        service.save()
        
        # Car status should be updated back to 'available'
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, 'available')

class RepairServiceModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
    
    def test_repair_service_creation(self):
        service = RepairService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Brake Repair',
            description='Replace brake pads',
            repair_type='brakes',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=150.00,
            labor_cost=100.00,
            status='scheduled'
        )
        self.assertEqual(service.customer, self.customer)
        self.assertEqual(service.car, self.car)
        self.assertEqual(service.title, 'Brake Repair')
        self.assertEqual(service.repair_type, 'brakes')
        self.assertEqual(service.status, 'scheduled')
    
    def test_repair_service_str_representation(self):
        service = RepairService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Brake Repair',
            description='Replace brake pads',
            repair_type='brakes',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=150.00,
            labor_cost=100.00,
            status='scheduled'
        )
        self.assertEqual(str(service), 'Brake Repair - Toyota Camry')
    
    def test_total_cost_calculation(self):
        service = RepairService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Brake Repair',
            description='Replace brake pads',
            repair_type='brakes',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=150.00,
            labor_cost=100.00,
            additional_fees=20.00,
            status='scheduled'
        )
        
        # Total cost should be sum of parts, labor, and fees
        self.assertEqual(service.total_cost, 270.00)
    
    def test_warranty_calculation(self):
        service = RepairService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Brake Repair',
            description='Replace brake pads',
            repair_type='brakes',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=150.00,
            labor_cost=100.00,
            warranty_period=90,
            status='scheduled'
        )
        
        # No warranty expiry initially
        self.assertIsNone(service.warranty_expiry)
        
        # Complete the service
        service.status = 'completed'
        service.completed_date = timezone.now()
        service.save()
        
        # Warranty expiry should be set to 90 days from completion
        service.refresh_from_db()
        expected_expiry = service.completed_date.date() + timedelta(days=90)
        self.assertEqual(service.warranty_expiry, expected_expiry)
        
        # Should be under warranty
        self.assertTrue(service.is_under_warranty)

class UpgradeServiceModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
    
    def test_upgrade_service_creation(self):
        service = UpgradeService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Performance Exhaust',
            description='Install performance exhaust system',
            upgrade_type='performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=500.00,
            labor_cost=200.00,
            horsepower_increase=15,
            status='scheduled'
        )
        self.assertEqual(service.customer, self.customer)
        self.assertEqual(service.car, self.car)
        self.assertEqual(service.title, 'Performance Exhaust')
        self.assertEqual(service.upgrade_type, 'performance')
        self.assertEqual(service.horsepower_increase, 15)
        self.assertEqual(service.status, 'scheduled')
    
    def test_upgrade_service_str_representation(self):
        service = UpgradeService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Performance Exhaust',
            description='Install performance exhaust system',
            upgrade_type='performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=500.00,
            labor_cost=200.00,
            horsepower_increase=15,
            status='scheduled'
        )
        self.assertEqual(str(service), 'Performance Exhaust - Toyota Camry')
    
    def test_total_cost_calculation(self):
        service = UpgradeService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Performance Exhaust',
            description='Install performance exhaust system',
            upgrade_type='performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=500.00,
            labor_cost=200.00,
            additional_fees=50.00,
            status='scheduled'
        )
        
        # Total cost should be sum of parts, labor, and fees
        self.assertEqual(service.total_cost, 750.00)
    
    def test_warranty_calculation(self):
        service = UpgradeService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Performance Exhaust',
            description='Install performance exhaust system',
            upgrade_type='performance',
            scheduled_date=timezone.now() + timedelta(days=1),
            parts_cost=500.00,
            labor_cost=200.00,
            warranty_period=365,
            status='scheduled'
        )
        
        # No warranty expiry initially
        self.assertIsNone(service.warranty_expiry)
        
        # Complete the service
        service.status = 'completed'
        service.completed_date = timezone.now()
        service.save()
        
        # Warranty expiry should be set to 365 days from completion
        service.refresh_from_db()
        expected_expiry = service.completed_date.date() + timedelta(days=365)
        self.assertEqual(service.warranty_expiry, expected_expiry)
        
        # Should be under warranty
        self.assertTrue(service.is_under_warranty)

class ConsultationServiceModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
    
    def test_consultation_service_creation(self):
        service = ConsultationService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Purchase Consultation',
            description='Discuss car purchase options',
            consultation_type='purchase',
            scheduled_date=timezone.now() + timedelta(days=1),
            consultation_fee=100.00,
            status='scheduled'
        )
        self.assertEqual(service.customer, self.customer)
        self.assertEqual(service.car, self.car)
        self.assertEqual(service.title, 'Purchase Consultation')
        self.assertEqual(service.consultation_type, 'purchase')
        self.assertEqual(service.status, 'scheduled')
    
    def test_consultation_service_str_representation(self):
        service = ConsultationService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Purchase Consultation',
            description='Discuss car purchase options',
            consultation_type='purchase',
            scheduled_date=timezone.now() + timedelta(days=1),
            consultation_fee=100.00,
            status='scheduled'
        )
        self.assertEqual(str(service), 'Purchase Consultation - John Doe')
    
    def test_consultation_without_car(self):
        service = ConsultationService.objects.create(
            customer=self.customer,
            car=None,
            title='General Consultation',
            description='General automotive advice',
            consultation_type='other',
            scheduled_date=timezone.now() + timedelta(days=1),
            consultation_fee=100.00,
            status='scheduled'
        )
        self.assertEqual(service.customer, self.customer)
        self.assertIsNone(service.car)
        self.assertEqual(service.title, 'General Consultation')
        self.assertEqual(service.consultation_type, 'other')
        self.assertEqual(service.status, 'scheduled')
    
    def test_follow_up_dates(self):
        service = ConsultationService.objects.create(
            customer=self.customer,
            car=self.car,
            title='Purchase Consultation',
            description='Discuss car purchase options',
            consultation_type='purchase',
            scheduled_date=timezone.now() + timedelta(days=1),
            consultation_fee=100.00,
            status='scheduled'
        )
        
        # No follow-up initially
        self.assertFalse(service.follow_up_required)
        self.assertIsNone(service.follow_up_date)
        
        # Set follow-up required
        service.follow_up_required = True
        service.follow_up_date = service.scheduled_date + timedelta(days=7)
        service.save()
        
        # Follow-up should be set
        service.refresh_from_db()
        self.assertTrue(service.follow_up_required)
        self.assertEqual(service.follow_up_date.date(), service.scheduled_date.date() + timedelta(days=7))

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.customer = Customer.objects.create(name='John Doe', email='john@example.com')
        self.car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
        
        # Create site info
        self.site_info = SiteInfo.objects.create(
            company_name='Test Car Rental',
            email='info@test.com'
        )

    def test_home_view(self):
        response = self.client.get(reverse('car_rental:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Car Rental')
    
    def test_car_list_view(self):
        response = self.client.get(reverse('car_rental:all_cars'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota Camry')
    
    def test_car_detail_view(self):
        response = self.client.get(reverse('car_rental:car_detail', kwargs={'pk': self.car.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota Camry')
    
    def test_rent_cars_view(self):
        response = self.client.get(reverse('car_rental:rent_cars'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota Camry')
    
    def test_sale_cars_view(self):
        # Update car for sale
        self.car.for_rent = False
        self.car.for_sale = True
        self.car.sale_price = 25000.00
        self.car.save()
        
        response = self.client.get(reverse('car_rental:sale_cars'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota Camry')
    
    def test_search_view(self):
        response = self.client.get(reverse('car_rental:search'), {'q': 'Toyota'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota Camry')
    
    def test_services_overview_view(self):
        response = self.client.get(reverse('car_rental:services_overview'))
        self.assertEqual(response.status_code, 200)
    
    def test_diagnostic_services_view(self):
        response = self.client.get(reverse('car_rental:diagnostic_services'))
        self.assertEqual(response.status_code, 200)
    
    def test_repair_services_view(self):
        response = self.client.get(reverse('car_rental:repair_services'))
        self.assertEqual(response.status_code, 200)
    
    def test_upgrade_services_view(self):
        response = self.client.get(reverse('car_rental:upgrade_services'))
        self.assertEqual(response.status_code, 200)
    
    def test_consultation_services_view(self):
        response = self.client.get(reverse('car_rental:consultation_services'))
        self.assertEqual(response.status_code, 200)
    
    def test_login_view(self):
        response = self.client.get(reverse('car_rental:login'))
        self.assertEqual(response.status_code, 200)
        
        # Test login with valid credentials
        response = self.client.post(reverse('car_rental:login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login
    
    def test_register_view(self):
        response = self.client.get(reverse('car_rental:register'))
        self.assertEqual(response.status_code, 200)
        
        # Test registration with valid data
        response = self.client.post(reverse('car_rental:register'), {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after registration
    
    def test_profile_view_requires_login(self):
        response = self.client.get(reverse('car_rental:profile'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Login and try again
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('car_rental:profile'))
        self.assertEqual(response.status_code, 200)

class FormTests(TestCase):
    def test_car_form_valid_data(self):
        form_data = {
            'make': 'Toyota',
            'model': 'Camry',
            'year': 2022,
            'default_price': 50.00,
            'description': 'A reliable sedan',
            'for_rent': True,
            'rent_price': 60.00,
            'status': 'available'
        }
        form = CarForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_car_form_invalid_data(self):
        # Missing required fields
        form_data = {
            'make': 'Toyota',
            'model': 'Camry',
            # Missing year, price, etc.
        }
        form = CarForm(data=form_data)
        self.assertFalse(form.is_valid())
    
    def test_rental_form_valid_data(self):
        customer = Customer.objects.create(name='John Doe', email='john@example.com')
        car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
        
        form_data = {
            'customer': customer.pk,
            'car': car.pk,
            'rental_datetime': timezone.now(),
            'return_datetime': timezone.now() + timedelta(days=3),
            'daily_rate': 60.00,
            'status': 'active'
        }
        form = RentalForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_rental_form_invalid_dates(self):
        customer = Customer.objects.create(name='John Doe', email='john@example.com')
        car = Car.objects.create(
            make='Toyota',
            model='Camry',
            year=2022,
            default_price=50.00,
            description='A reliable sedan',
            for_rent=True,
            rent_price=60.00,
            status='available'
        )
        
        # Return date before rental date
        form_data = {
            'customer': customer.pk,
            'car': car.pk,
            'rental_datetime': timezone.now(),
            'return_datetime': timezone.now() - timedelta(days=3),
            'daily_rate': 60.00,
            'status': 'active'
        }
        form = RentalForm(data=form_data)
        self.assertFalse(form.is_valid())

class UtilsTests(TestCase):
    def test_calculate_distance(self):
        # Distance between New York and Los Angeles (approximately 3935 km)
        ny_lat, ny_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437
        
        distance = calculate_distance(ny_lat, ny_lon, la_lat, la_lon)
        
        # Should be approximately 3935 km (allowing for some variation)
        self.assertTrue(3900 < distance < 4000)
    
    def test_format_currency(self):
        self.assertEqual(format_currency(1234.56), '$1,234.56')
        self.assertEqual(format_currency(50), '$50.00')
        self.assertEqual(format_currency(0.99), '$0.99')
    
    def test_generate_invoice_number(self):
        # This test would need to be adjusted based on your actual model structure
        # For now, we'll just test the basic format
        prefix = 'INV'
        model = Car  # This is just a placeholder
        
        invoice_number = generate_invoice_number(prefix, model)
        
        # Should start with the prefix
        self.assertTrue(invoice_number.startswith(prefix))
        
        # Should include today's date
        today_str = timezone.now().strftime('%Y%m%d')
        self.assertIn(today_str, invoice_number)
        
        # Should end with a 4-digit number
        self.assertTrue(invoice_number[-4:].isdigit())