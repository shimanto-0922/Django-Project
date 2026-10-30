from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.http import urlencode

from properties.models import Amenity, Property

from .matching import MatchEngine


class SearchCriteria(models.Model):
    """A saved set of preferences a tenant can re-run at any time."""

    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='search_criteria')
    name = models.CharField(max_length=80, help_text='e.g. "Near office" or "Family flat under 30k"')
    keyword = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=10, choices=Property.Category.choices, blank=True)
    property_type = models.CharField(max_length=12, choices=Property.PropertyType.choices, blank=True)
    min_price = models.PositiveIntegerField(null=True, blank=True)
    max_price = models.PositiveIntegerField(null=True, blank=True)
    budget_includes_bills = models.BooleanField(
        default=False, help_text='Compare the budget with rent + service charge + utilities.',
    )
    min_bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    min_bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    needs_parking = models.BooleanField('Parking required', default=False)
    needs_pet_friendly = models.BooleanField('Pet friendly required', default=False)
    needs_furnished = models.BooleanField('Furnished required', default=False)
    tenant_gender = models.CharField(
        'I am', max_length=6, blank=True, choices=[('male', 'Male'), ('female', 'Female')],
        help_text='Hides male-only or female-only listings that do not fit you.',
    )
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'search criteria'

    def __str__(self):
        return f'{self.name} ({self.tenant})'

    PREFERENCE_FIELDS = (
        'keyword', 'location', 'category', 'property_type', 'min_price', 'max_price',
        'budget_includes_bills', 'min_bedrooms', 'min_bathrooms',
        'needs_parking', 'needs_pet_friendly', 'needs_furnished', 'tenant_gender',
    )

    def as_preferences(self):
        prefs = {name: getattr(self, name) for name in self.PREFERENCE_FIELDS}
        prefs['amenities'] = list(self.amenities.all()) if self.pk else []
        return prefs

    def engine(self):
        return MatchEngine(self.as_preferences())

    def execute_basic_search(self):
        return self.engine().strict_filter(Property.objects.visible().prefetch_related('images', 'amenities', 'utilities'))

    def calculate_match_percentage(self, prop):
        return self.engine().score(prop).percentage

    def get_search_url(self):
        params = {k: v for k, v in self.as_preferences().items() if v not in (None, '', False, [])}
        params['amenities'] = [a.pk for a in params.get('amenities', [])]
        for flag in ('budget_includes_bills', 'needs_parking', 'needs_pet_friendly', 'needs_furnished'):
            if flag in params:
                params[flag] = 'on'
        return f"{reverse('search:search')}?{urlencode(params, doseq=True)}"

    @property
    def summary(self):
        bits = []
        if self.location:
            bits.append(self.location)
        if self.category:
            bits.append(self.get_category_display())
        if self.max_price:
            bits.append(f'up to {self.max_price:,} BDT')
        if self.min_bedrooms:
            bits.append(f'{self.min_bedrooms}+ beds')
        return ' · '.join(bits) or 'Any property'
