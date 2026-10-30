from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Avg
from django.urls import reverse

POPULAR_AREAS = [
    'Dhanmondi', 'Gulshan', 'Banani', 'Uttara', 'Mirpur', 'Mohammadpur', 'Bashundhara',
    'Farmgate', 'Tejgaon', 'Badda', 'Rampura', 'Khilgaon', 'Motijheel', 'Shantinagar',
    'Malibagh', 'Baridhara', 'Lalmatia', 'Shyamoli', 'Agargaon', 'Wari', 'Old Dhaka',
    'Agrabad', 'Nasirabad', 'Khulshi', 'Zindabazar', 'Ambarkhana', 'Sonadanga', 'Shaheb Bazar',
]

# Categories where it makes sense to restrict tenants by gender.
GENDER_RESTRICTABLE = ('bachelor', 'sublet', 'hostel')

# Icon + short description for every listing category (used across the UI).
CATEGORY_META = {
    'family': ('bi-house-heart', 'Flats and houses for families'),
    'bachelor': ('bi-person-badge', 'For students and job holders'),
    'sublet': ('bi-door-open', 'A room inside a family home'),
    'hostel': ('bi-buildings', 'Mess and hostel seats'),
    'office': ('bi-briefcase', 'Office floors and spaces'),
    'shop': ('bi-shop', 'Shops and commercial units'),
}


class Amenity(models.Model):
    name = models.CharField(max_length=60, unique=True)
    icon = models.CharField(max_length=40, default='bi-check2-circle', help_text='Bootstrap icon class, e.g. bi-wifi')
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'amenities'

    def __str__(self):
        return self.name


class PropertyQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(status=Property.Status.APPROVED)

    def visible(self):
        """Listings a tenant is allowed to browse."""
        return self.approved().filter(is_available=True)

    def with_ratings(self):
        return self.annotate(avg_rating=Avg('reviews__rating'))


class Property(models.Model):
    class PropertyType(models.TextChoices):
        APARTMENT = 'apartment', 'Apartment / Flat'
        HOUSE = 'house', 'Full house'
        ROOM = 'room', 'Single room'
        STUDIO = 'studio', 'Studio'
        DUPLEX = 'duplex', 'Duplex'
        SEAT = 'seat', 'Seat (shared room)'
        COMMERCIAL = 'commercial', 'Commercial space'

    class Category(models.TextChoices):
        FAMILY = 'family', 'Family'
        BACHELOR = 'bachelor', 'Bachelor'
        SUBLET = 'sublet', 'Sublet'
        HOSTEL = 'hostel', 'Hostel / Mess'
        OFFICE = 'office', 'Office'
        SHOP = 'shop', 'Shop'

    class Division(models.TextChoices):
        DHAKA = 'dhaka', 'Dhaka'
        CHATTOGRAM = 'chattogram', 'Chattogram'
        KHULNA = 'khulna', 'Khulna'
        RAJSHAHI = 'rajshahi', 'Rajshahi'
        SYLHET = 'sylhet', 'Sylhet'
        BARISHAL = 'barishal', 'Barishal'
        RANGPUR = 'rangpur', 'Rangpur'
        MYMENSINGH = 'mymensingh', 'Mymensingh'

    class Gender(models.TextChoices):
        ANY = 'any', 'Anyone'
        MALE = 'male', 'Male only'
        FEMALE = 'female', 'Female only'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Published'
        REJECTED = 'rejected', 'Rejected'

    landlord = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=150)
    description = models.TextField()
    property_type = models.CharField(max_length=12, choices=PropertyType.choices, default=PropertyType.APARTMENT)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.FAMILY)

    division = models.CharField(max_length=12, choices=Division.choices, default=Division.DHAKA)
    city = models.CharField('City / district', max_length=60, default='Dhaka')
    location = models.CharField('Area', max_length=80, help_text='Neighbourhood, e.g. Dhanmondi')
    address = models.CharField(max_length=255, help_text='Road / house number. Shown only to tenants after approval.')

    price = models.PositiveIntegerField('Monthly rent (BDT)', validators=[MinValueValidator(500)])
    is_negotiable = models.BooleanField('Rent is negotiable', default=False)
    service_charge = models.PositiveIntegerField('Service charge (BDT / month)', default=0)
    advance_months = models.PositiveSmallIntegerField('Advance (months)', default=2)

    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    balconies = models.PositiveSmallIntegerField(default=0)
    floor = models.SmallIntegerField(default=1, help_text='0 for ground floor')
    size = models.PositiveIntegerField('Size (sq ft)', null=True, blank=True)
    furnished = models.BooleanField(default=False)
    pet_friendly = models.BooleanField(default=False)
    parking = models.BooleanField(default=False)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='properties')
    tenant_gender = models.CharField(
        'Who can rent', max_length=6, choices=Gender.choices, default=Gender.ANY,
        help_text='Only for bachelor, sublet and hostel listings.',
    )

    house_rules = models.TextField(blank=True, help_text='Guest policy, smoking, cooking rules, etc.')
    gate_closing_time = models.TimeField(null=True, blank=True)
    available_from = models.DateField(null=True, blank=True)
    is_available = models.BooleanField(default=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    moderation_note = models.CharField(max_length=255, blank=True)
    is_featured = models.BooleanField(default=False, help_text='Featured listings are shown first.')
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PropertyQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'properties'
        indexes = [models.Index(fields=['status', 'is_available', 'location'])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('properties:detail', args=[self.pk])

    # ---- cost helpers -------------------------------------------------
    @property
    def utilities_monthly_total(self):
        return sum((u.monthly_amount() for u in self.utilities.all() if not u.included_in_rent), Decimal('0'))

    @property
    def monthly_cost(self):
        """Rent + service charge + every utility the tenant has to pay separately."""
        return Decimal(self.price) + Decimal(self.service_charge) + self.utilities_monthly_total

    @property
    def advance_amount(self):
        return self.price * self.advance_months

    # ---- display helpers ----------------------------------------------
    @property
    def primary_image(self):
        images = list(self.images.all())
        for image in images:
            if image.is_primary:
                return image
        return images[0] if images else None

    @property
    def average_rating(self):
        value = getattr(self, 'avg_rating', None)
        if value is None:
            value = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(value, 1) if value else None

    @property
    def reference_code(self):
        return f'GH-{self.pk:05d}' if self.pk else 'GH-NEW'

    @property
    def full_location(self):
        parts = [self.location, self.city]
        if self.get_division_display() != self.city:
            parts.append(self.get_division_display())
        return ', '.join(parts)

    @property
    def is_commercial(self):
        return self.category in (self.Category.OFFICE, self.Category.SHOP)

    def accepts_gender(self, gender):
        return self.tenant_gender == self.Gender.ANY or not gender or self.tenant_gender == gender

    @property
    def floor_label(self):
        return 'Ground floor' if self.floor == 0 else f'Floor {self.floor}'

    @property
    def is_published(self):
        return self.status == self.Status.APPROVED

    def is_owned_by(self, user):
        return user.is_authenticated and self.landlord_id == user.id


def property_image_path(instance, filename):
    return f'properties/{instance.property_id}/{filename}'


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=property_image_path)
    caption = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'uploaded_at']

    def __str__(self):
        return f'Image for {self.property}'

    def save(self, *args, **kwargs):
        # Only one cover photo per property.
        if self.is_primary:
            PropertyImage.objects.filter(property=self.property, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        storage, path = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if path:
            storage.delete(path)


class Utility(models.Model):
    class Kind(models.TextChoices):
        ELECTRICITY = 'electricity', 'Electricity'
        GAS = 'gas', 'Gas'
        WATER = 'water', 'Water'
        INTERNET = 'internet', 'Internet'
        GARBAGE = 'garbage', 'Garbage / cleaning'
        SECURITY = 'security', 'Security guard'
        OTHER = 'other', 'Other'

    class Period(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='utilities')
    name = models.CharField(max_length=15, choices=Kind.choices)
    amount = models.DecimalField('Estimated amount (BDT)', max_digits=9, decimal_places=2, validators=[MinValueValidator(0)])
    billing_period = models.CharField(max_length=8, choices=Period.choices, default=Period.MONTHLY)
    included_in_rent = models.BooleanField(default=False, help_text='Tick if the rent already covers this bill.')
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'utilities'

    def __str__(self):
        return f'{self.get_name_display()} - {self.property}'

    def monthly_amount(self):
        if self.billing_period == self.Period.YEARLY:
            return (self.amount / 12).quantize(Decimal('0.01'))
        return self.amount
