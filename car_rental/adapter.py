from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.html import strip_tags
from allauth.account.signals import password_changed

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Extends the DefaultAccountAdapter to add a password change email,
    while keeping all other default allauth functionality intact.
    """
    
    def send_password_change_email(self, request, user):
        """
        Sends a confirmation email to the user after their password has been changed.
        """
        site = get_current_site(request)
        subject = f"Your {site.name} Password Has Been Changed"
        
        context = {
            'user': user,
            'site_name': site.name,
            'site_url': settings.SITE_URL,
        }
        
        html_message = render_to_string('emails/password_change_email.html', context)
        plain_message = strip_tags(html_message)
        
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [user.email]
        
        send_mail(subject, plain_message, from_email, to_email, html_message=html_message, fail_silently=False)

# --- Create a standalone receiver function ---
def password_change_email_receiver(sender, request, user, **kwargs):
    """
    A standalone receiver function that connects to the signal and calls the adapter method.
    """
    # Get an instance of our custom adapter
    adapter = CustomAccountAdapter()
    # Call the method on the instance, passing the arguments
    adapter.send_password_change_email(request, user)
# ------------------------------------------------

# --- Connect the signal to our new receiver function ---
# This is the correct way to connect to signals that send **kwargs**.
password_changed.connect(password_change_email_receiver)
# -------------------------------------------------