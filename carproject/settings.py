"""
Django settings for carproject project.
"""

import os
from pathlib import Path
import cloudinary
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Allauth apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google', # Added the Google provider explicitly
    
    # Custom apps & 3rd party
    'car_rental',
    'cloudinary_storage',
    'cloudinary',
]

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # `allauth` specific authentication methods, such as login by e-mail
    'allauth.account.auth_backends.AuthenticationBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'carproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'car_rental', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'car_rental.context_processors.get_site_info_context',
                'car_rental.context_processors.marketing_keys',
            ],
        },
    },
]

WSGI_APPLICATION = 'carproject.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # Make sure this points to your static directory
]
STATIC_ROOT = BASE_DIR / 'staticfiles'  # For production

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SITE_ID = 1  # Required for django-allauth
SITE_URL = 'http://localhost:8000'


# ==========================================
# --- DJANGO-ALLAUTH & GOOGLE SETTINGS ---
# ==========================================

LOGIN_REDIRECT_URL = '/profile'
LOGOUT_REDIRECT_URL = '/'

# Base Account Settings
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'mandatory' # Standard users must verify
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
# Tells Django to automatically link Google logins to existing accounts with the same email
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Custom Adapters
EMAIL_ADAPTER = 'allauth.account.adapters.DefaultAccountAdapter'
ACCOUNT_ADAPTER = 'car_rental.adapter.CustomAccountAdapter'

# Google Social Account Settings
SOCIALACCOUNT_GOOGLE_CLIENT_ID = os.environ.get('SOCIALACCOUNT_GOOGLE_CLIENT_ID', '')
SOCIALACCOUNT_GOOGLE_CLIENT_SECRET = os.environ.get('SOCIALACCOUNT_GOOGLE_CLIENT_SECRET', '')

# Force 1-click seamless registration for Google users
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none' # Google already verified their email!

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': SOCIALACCOUNT_GOOGLE_CLIENT_ID,
            'secret': SOCIALACCOUNT_GOOGLE_CLIENT_SECRET,
        }
    }
}


# ==========================================
# --- EXTERNAL APIS & MARKETING ---
# ==========================================

# Marketing IDs
GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID', '')
META_PIXEL_ID = os.environ.get('META_PIXEL_ID', '')

# Cloudinary
cloudinary.config(
    cloud_name= os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key= os.environ.get('CLOUDINARY_API_KEY'),
    api_secret= os.environ.get('CLOUDINARY_API_SECRET'),
)

CLOUDINARY = {
    'DEFAULT_FILE_TRANSFORMATIONS': {
        'quality': 'auto:best',  # Automatically optimize quality
        'fetch_format': 'auto'   # Automatically choose best format (WebP, JPEG, etc.)
    }
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('MY_EMAIL_ADDRESS')
EMAIL_HOST_PASSWORD = os.environ.get('YOUR_EMAIL_PASSWORD')

DEFAULT_FROM_EMAIL = os.environ.get('MY_EMAIL_ADDRESS')
MANAGEMENT_EMAIL = os.environ.get('MY_EMAIL_ADDRESS') 

# Custom error handlers
HANDLER403 = 'car_rental.views.permission_denied'
HANDLER404 = 'car_rental.views.page_not_found'
HANDLER500 = 'car_rental.views.server_error'