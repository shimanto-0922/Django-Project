from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r'^(\+?88)?01[3-9]\d{8}$',
    message='Enter a valid Bangladeshi mobile number, e.g. 01712345678.',
)


def avatar_upload_path(instance, filename):
    return f'avatars/user_{instance.pk or "new"}/{filename}'


def verification_upload_path(instance, filename):
    return f'verification/landlord_{instance.user_id}/{filename}'


class GhorifyUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """A single user table for every person on the platform.

    The `role` field decides whether the person acts as a tenant, a landlord or a
    platform admin. Role-specific data lives in TenantProfile / LandlordProfile.
    """

    objects = GhorifyUserManager()

    class Role(models.TextChoices):
        TENANT = 'tenant', 'Tenant'
        LANDLORD = 'landlord', 'Landlord'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.TENANT)
    phone = models.CharField(max_length=14, blank=True, validators=[phone_validator])
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_tenant(self):
        return self.role == self.Role.TENANT

    @property
    def is_landlord(self):
        return self.role == self.Role.LANDLORD

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        name = self.display_name.split()
        return ''.join(part[0] for part in name[:2]).upper()


class TenantProfile(models.Model):
    class Occupation(models.TextChoices):
        STUDENT = 'student', 'Student'
        PROFESSIONAL = 'professional', 'Job holder'
        BUSINESS = 'business', 'Business'
        OTHER = 'other', 'Other'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_profile')
    preferred_location = models.CharField(max_length=120, blank=True)
    occupation = models.CharField(max_length=20, choices=Occupation.choices, default=Occupation.OTHER)
    family_size = models.PositiveSmallIntegerField(default=1)
    monthly_budget = models.PositiveIntegerField(null=True, blank=True, help_text='Maximum rent you can pay (BDT).')

    def __str__(self):
        return f'Tenant profile of {self.user}'


class LandlordProfile(models.Model):
    class Status(models.TextChoices):
        UNSUBMITTED = 'unsubmitted', 'Documents not submitted'
        PENDING = 'pending', 'Waiting for review'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='landlord_profile')
    nid_number = models.CharField('NID number', max_length=20, blank=True)
    verification_docs = models.FileField(
        upload_to=verification_upload_path, blank=True, null=True,
        help_text='NID or ownership paper (PDF/JPG/PNG).',
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNSUBMITTED)
    review_note = models.CharField(max_length=255, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_landlords',
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Landlord profile of {self.user}'

    @property
    def is_verified(self):
        return self.status == self.Status.VERIFIED

    def mark_verified(self, admin_user):
        self.status = self.Status.VERIFIED
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.review_note = ''
        self.save()

    def mark_rejected(self, admin_user, note=''):
        self.status = self.Status.REJECTED
        self.verified_by = admin_user
        self.verified_at = None
        self.review_note = note
        self.save()
