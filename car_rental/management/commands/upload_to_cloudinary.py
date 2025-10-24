# In management/commands/upload_to_cloudinary.py
from django.core.management.base import BaseCommand
from django.core.files import File
from cloudinary.uploader import upload
from car_rental.models import Car, UserProfile, SiteInfo, Customer
import os

class Command(BaseCommand):
    help = 'Upload existing media files to Cloudinary'
    
    def handle(self, *args, **options):
        # Upload Car images
        for car in Car.objects.all():
            if car.image and hasattr(car.image, 'path'):
                with open(car.image.path, 'rb') as f:
                    result = upload(f, folder='cars/', 
                                 transformation={'quality': 'auto:best', 'fetch_format': 'auto'})
                    car.image = result['public_id']
                    car.save()
        
        # Repeat for other models with images...
        self.stdout.write(self.style.SUCCESS('Successfully uploaded media to Cloudinary'))