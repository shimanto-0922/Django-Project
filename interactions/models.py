from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from properties.models import Property

MAX_COMPARE_ITEMS = 3


class Favourite(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favourites')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='favourited_by')
    note = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['tenant', 'property'], name='unique_favourite')]

    def __str__(self):
        return f'{self.tenant} likes {self.property}'


class Comparison(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comparisons')
    name = models.CharField(max_length=80, default='My comparison')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.name} ({self.tenant})'

    @property
    def is_full(self):
        return self.items.count() >= MAX_COMPARE_ITEMS

    def properties(self):
        return [item.property for item in self.items.select_related('property').order_by('position')]

    def add(self, prop):
        """Add a property; returns (ok, message)."""
        if self.items.filter(property=prop).exists():
            return False, 'This property is already in the comparison.'
        if self.is_full:
            return False, f'You can compare up to {MAX_COMPARE_ITEMS} properties. Remove one first.'
        position = (self.items.aggregate(models.Max('position'))['position__max'] or 0) + 1
        ComparisonItem.objects.create(comparison=self, property=prop, position=position)
        self.save(update_fields=['updated_at'])
        return True, f'"{prop.title}" added to {self.name}.'


class ComparisonItem(models.Model):
    comparison = models.ForeignKey(Comparison, on_delete=models.CASCADE, related_name='items')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='comparison_items')
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['comparison', 'property'], name='unique_comparison_property')]

    def __str__(self):
        return f'{self.property} in {self.comparison}'


class RequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'


ACTIVE_STATUSES = (RequestStatus.PENDING, RequestStatus.APPROVED)


class VisitRequest(models.Model):
    class TimeSlot(models.TextChoices):
        MORNING = 'morning', 'Morning (9 AM - 12 PM)'
        AFTERNOON = 'afternoon', 'Afternoon (12 PM - 4 PM)'
        EVENING = 'evening', 'Evening (4 PM - 8 PM)'

    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='visit_requests')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='visit_requests')
    preferred_date = models.DateField()
    time_slot = models.CharField(max_length=10, choices=TimeSlot.choices)
    message = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=RequestStatus.choices, default=RequestStatus.PENDING)
    landlord_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Visit to {self.property} on {self.preferred_date}'

    def is_pending(self):
        return self.status == RequestStatus.PENDING


class RentalRequest(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rental_requests')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='rental_requests')
    move_in_date = models.DateField()
    duration_months = models.PositiveSmallIntegerField(default=12, validators=[MinValueValidator(1), MaxValueValidator(60)])
    occupants = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(20)])
    message = models.TextField(blank=True, max_length=600)
    status = models.CharField(max_length=10, choices=RequestStatus.choices, default=RequestStatus.PENDING)
    landlord_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Rental request for {self.property} by {self.tenant}'

    def is_pending(self):
        return self.status == RequestStatus.PENDING


class Review(models.Model):
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    landlord_rating = models.PositiveSmallIntegerField(
        'Landlord behaviour', validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True,
    )
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['tenant', 'property'], name='one_review_per_property')]

    def __str__(self):
        return f'{self.rating}/5 for {self.property}'


class Report(models.Model):
    class Reason(models.TextChoices):
        NOT_AVAILABLE = 'not_available', 'Property is not available any more'
        UNREACHABLE = 'unreachable', 'Landlord phone is unreachable'
        LOCATION = 'location', 'Location does not match'
        RENT = 'rent', 'Rent amount does not match'
        PHOTOS = 'photos', 'Photos do not match the property'
        FAKE = 'fake', 'Fake or non-existent listing'
        SCAM = 'scam', 'Asked for money before a visit'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Action taken'
        DISMISSED = 'dismissed', 'Dismissed'

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=15, choices=Reason.choices)
    details = models.TextField(max_length=800, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    admin_note = models.CharField(max_length=255, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Report on {self.property}: {self.get_reason_display()}'
