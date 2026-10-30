from django import forms

from properties.models import POPULAR_AREAS, Amenity

from .models import SearchCriteria


class SearchCriteriaForm(forms.ModelForm):
    class Meta:
        model = SearchCriteria
        fields = (
            'name', 'keyword', 'location', 'category', 'property_type',
            'min_price', 'max_price', 'budget_includes_bills',
            'min_bedrooms', 'min_bathrooms', 'tenant_gender',
            'needs_parking', 'needs_pet_friendly', 'needs_furnished', 'amenities',
        )
        labels = {'min_bedrooms': 'Min beds', 'min_bathrooms': 'Min baths', 'property_type': 'Type'}
        widgets = {
            'location': forms.TextInput(attrs={'list': 'area-list', 'autocomplete': 'off', 'placeholder': 'Any area'}),
            'keyword': forms.TextInput(attrs={'placeholder': 'e.g. lake view, near university'}),
            'min_price': forms.NumberInput(attrs={'placeholder': 'Min'}),
            'max_price': forms.NumberInput(attrs={'placeholder': 'Max'}),
            'amenities': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, require_name=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = require_name
        self.fields['amenities'].queryset = Amenity.objects.all()
        self.fields['category'].choices = [('', 'Any')] + list(self.fields['category'].choices)[1:]
        self.fields['property_type'].choices = [('', 'Any')] + list(self.fields['property_type'].choices)[1:]
        self.fields['tenant_gender'].choices = [('', 'Prefer not to say')] + list(self.fields['tenant_gender'].choices)[1:]
        self.area_suggestions = POPULAR_AREAS

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get('min_price'), cleaned.get('max_price')
        if low and high and low > high:
            self.add_error('max_price', 'Maximum rent must be higher than the minimum.')
        return cleaned

    def preferences(self):
        data = dict(self.cleaned_data)
        data.pop('name', None)
        data['amenities'] = list(data.get('amenities') or [])
        return data
