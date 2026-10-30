from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LandlordProfile, TenantProfile, User


@receiver(post_save, sender=User)
def create_role_profile(sender, instance, created, **kwargs):
    """Make sure every tenant/landlord always has its matching profile row."""
    if instance.role == User.Role.TENANT:
        TenantProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.LANDLORD:
        LandlordProfile.objects.get_or_create(user=instance)
