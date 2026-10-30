from django import forms
from django.conf import settings

from .models import GENDER_RESTRICTABLE, POPULAR_AREAS, Amenity, Property, PropertyImage, Utility

MAX_IMAGES_PER_PROPERTY = 10


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """An ImageField that accepts several files from one <input multiple>."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)] if data else []


def check_image_sizes(images):
    for image in images:
        if image.size > settings.MAX_UPLOAD_SIZE:
            raise forms.ValidationError(f'"{image.name}" is larger than 5 MB.')
    return images


class PropertyForm(forms.ModelForm):
    photos = MultipleImageField(required=False, help_text='You can select several photos at once (max 5 MB each).')

    class Meta:
        model = Property
        fields = (
            'title', 'property_type', 'category', 'tenant_gender', 'description',
            'division', 'city', 'location', 'address',
            'price', 'is_negotiable', 'service_charge', 'advance_months',
            'bedrooms', 'bathrooms', 'balconies', 'floor', 'size',
            'furnished', 'pet_friendly', 'parking', 'amenities',
            'house_rules', 'gate_closing_time', 'available_from', 'is_available',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'house_rules': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. No guests after 10 PM, no smoking inside'}),
            'location': forms.TextInput(attrs={'list': 'area-list', 'autocomplete': 'off'}),
            'gate_closing_time': forms.TimeInput(attrs={'type': 'time'}),
            'available_from': forms.DateInput(attrs={'type': 'date'}),
            'amenities': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amenities'].queryset = Amenity.objects.all()
        self.area_suggestions = POPULAR_AREAS

    def clean_photos(self):
        photos = check_image_sizes(self.cleaned_data.get('photos') or [])
        existing = self.instance.images.count() if self.instance.pk else 0
        if existing + len(photos) > MAX_IMAGES_PER_PROPERTY:
            raise forms.ValidationError(f'A property can have at most {MAX_IMAGES_PER_PROPERTY} photos.')
        return photos

    def clean(self):
        cleaned = super().clean()
        category, bedrooms = cleaned.get('category'), cleaned.get('bedrooms')
        if category == Property.Category.FAMILY and bedrooms == 0:
            self.add_error('bedrooms', 'A family listing needs at least one bedroom.')
        gender = cleaned.get('tenant_gender')
        if gender and gender != Property.Gender.ANY and category not in GENDER_RESTRICTABLE:
            self.add_error('tenant_gender', 'Gender preference can only be set for bachelor, sublet or hostel listings.')
        if category == Property.Category.HOSTEL and cleaned.get('property_type') not in (
                Property.PropertyType.SEAT, Property.PropertyType.ROOM):
            self.add_error('property_type', 'Hostel listings should be a seat or a room.')
        if category in (Property.Category.OFFICE, Property.Category.SHOP) and cleaned.get('pet_friendly'):
            cleaned['pet_friendly'] = False
        return cleaned


class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ('image', 'caption', 'is_primary')

    def clean_image(self):
        image = self.cleaned_data.get('image')
        check_image_sizes([image] if image else [])
        return image


class UtilityForm(forms.ModelForm):
    class Meta:
        model = Utility
        fields = ('name', 'amount', 'billing_period', 'included_in_rent', 'note')

    def __init__(self, *args, property_obj=None, **kwargs):
        self.property_obj = property_obj
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name']
        prop = self.property_obj or getattr(self.instance, 'property', None)
        if prop and name != Utility.Kind.OTHER:
            clash = prop.utilities.filter(name=name).exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError('This utility is already listed. Edit the existing one instead.')
        return name


class BrowseFilterForm(forms.Form):
    SORT_CHOICES = [
        ('recommended', 'Featured first'),
        ('newest', 'Newest first'),
        ('price_low', 'Rent: low to high'),
        ('price_high', 'Rent: high to low'),
        ('rating', 'Best rated'),
    ]
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Title or keyword'}))
    category = forms.ChoiceField(required=False, choices=[('', 'All categories')] + Property.Category.choices)
    division = forms.ChoiceField(required=False, choices=[('', 'All divisions')] + Property.Division.choices)
    location = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Dhanmondi', 'list': 'area-list', 'autocomplete': 'off'}))
    property_type = forms.ChoiceField(required=False, choices=[('', 'Any type')] + Property.PropertyType.choices)
    min_price = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Min'}))
    max_price = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Max'}))
    bedrooms = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Any'}))
    bathrooms = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Any'}))
    gender = forms.ChoiceField(required=False, choices=[('', 'Anyone'), ('male', 'Male'), ('female', 'Female')],
                               label='Rent to')
    negotiable = forms.BooleanField(required=False, label='Negotiable rent')
    furnished = forms.BooleanField(required=False)
    parking = forms.BooleanField(required=False)
    verified = forms.BooleanField(required=False, label='Verified landlord')
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)

    def apply(self, qs):
        """Narrow a Property queryset with the submitted filters."""
        from django.db.models import F, Q
        data = self.cleaned_data
        if data.get('q'):
            q = data['q']
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(location__icontains=q))
        exact = {'category': 'category', 'division': 'division', 'property_type': 'property_type'}
        for field, lookup in exact.items():
            if data.get(field):
                qs = qs.filter(**{lookup: data[field]})
        if data.get('location'):
            qs = qs.filter(Q(location__icontains=data['location']) | Q(city__icontains=data['location']))
        if data.get('min_price'):
            qs = qs.filter(price__gte=data['min_price'])
        if data.get('max_price'):
            qs = qs.filter(price__lte=data['max_price'])
        if data.get('bedrooms'):
            qs = qs.filter(bedrooms__gte=data['bedrooms'])
        if data.get('bathrooms'):
            qs = qs.filter(bathrooms__gte=data['bathrooms'])
        if data.get('gender'):
            qs = qs.filter(tenant_gender__in=[Property.Gender.ANY, data['gender']])
        for flag, field in (('negotiable', 'is_negotiable'), ('furnished', 'furnished'), ('parking', 'parking')):
            if data.get(flag):
                qs = qs.filter(**{field: True})
        if data.get('verified'):
            qs = qs.filter(landlord__landlord_profile__status='verified')
        ordering = {
            'newest': ['-created_at'],
            'price_low': ['price'],
            'price_high': ['-price'],
            'rating': [F('avg_rating').desc(nulls_last=True), '-created_at'],
        }.get(data.get('sort'), ['-is_featured', '-created_at'])
        return qs.order_by(*ordering)
