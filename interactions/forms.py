from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import ACTIVE_STATUSES, Comparison, RentalRequest, Report, RequestStatus, Review, VisitRequest

MAX_VISIT_DAYS_AHEAD = 60


class VisitRequestForm(forms.ModelForm):
    class Meta:
        model = VisitRequest
        fields = ('preferred_date', 'time_slot', 'message')
        widgets = {
            'preferred_date': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.TextInput(attrs={'placeholder': 'Anything the landlord should know? (optional)'}),
        }

    def __init__(self, *args, tenant=None, property_obj=None, **kwargs):
        self.tenant, self.property_obj = tenant, property_obj
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['preferred_date'].widget.attrs.update({
            'min': (today + timedelta(days=1)).isoformat(),
            'max': (today + timedelta(days=MAX_VISIT_DAYS_AHEAD)).isoformat(),
        })

    def clean_preferred_date(self):
        date = self.cleaned_data['preferred_date']
        today = timezone.localdate()
        if date <= today:
            raise forms.ValidationError('Please pick a date from tomorrow onwards.')
        if date > today + timedelta(days=MAX_VISIT_DAYS_AHEAD):
            raise forms.ValidationError(f'Visits can be booked at most {MAX_VISIT_DAYS_AHEAD} days ahead.')
        return date

    def clean(self):
        cleaned = super().clean()
        prop = self.property_obj or getattr(self.instance, 'property', None)
        tenant = self.tenant or getattr(self.instance, 'tenant', None)
        date, slot = cleaned.get('preferred_date'), cleaned.get('time_slot')
        if not (prop and tenant):
            return cleaned
        if not self.instance.pk and VisitRequest.objects.filter(
                tenant=tenant, property=prop, status__in=ACTIVE_STATUSES).exists():
            raise forms.ValidationError('You already have an active visit request for this property.')
        if date and slot and VisitRequest.objects.filter(
                property=prop, preferred_date=date, time_slot=slot, status=RequestStatus.APPROVED,
        ).exclude(pk=self.instance.pk).exists():
            self.add_error('time_slot', 'This slot is already booked by another visitor. Try a different time.')
        return cleaned


class RentalRequestForm(forms.ModelForm):
    class Meta:
        model = RentalRequest
        fields = ('move_in_date', 'duration_months', 'occupants', 'message')
        widgets = {
            'move_in_date': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Introduce yourself: profession, family, etc.'}),
        }

    def __init__(self, *args, tenant=None, property_obj=None, **kwargs):
        self.tenant, self.property_obj = tenant, property_obj
        super().__init__(*args, **kwargs)
        self.fields['move_in_date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_move_in_date(self):
        date = self.cleaned_data['move_in_date']
        if date < timezone.localdate():
            raise forms.ValidationError('Move-in date cannot be in the past.')
        if self.property_obj and self.property_obj.available_from and date < self.property_obj.available_from:
            raise forms.ValidationError(
                f'This property is available from {self.property_obj.available_from:%d %b %Y}.')
        return date

    def clean(self):
        cleaned = super().clean()
        prop, tenant = self.property_obj, self.tenant
        if prop and tenant:
            if not prop.is_available:
                raise forms.ValidationError('This property has already been rented out.')
            if RentalRequest.objects.filter(tenant=tenant, property=prop, status__in=ACTIVE_STATUSES).exists():
                raise forms.ValidationError('You already have an active rental request for this property.')
            occupants = cleaned.get('occupants')
            if occupants and prop.category == 'sublet' and occupants > 2:
                self.add_error('occupants', 'Sublets usually allow at most 2 occupants.')
        return cleaned


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'landlord_rating', 'comment')
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, i) for i in range(5, 0, -1)]),
            'landlord_rating': forms.RadioSelect(choices=[(i, i) for i in range(5, 0, -1)]),
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'How was the house, the area and the landlord?'}),
        }

    def clean_comment(self):
        comment = self.cleaned_data['comment'].strip()
        if len(comment) < 15:
            raise forms.ValidationError('Please write at least a couple of sentences (15+ characters).')
        return comment


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ('reason', 'details')
        widgets = {'details': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Explain what is wrong (optional)'})}


class ComparisonForm(forms.ModelForm):
    class Meta:
        model = Comparison
        fields = ('name',)


class LandlordResponseForm(forms.Form):
    decision = forms.ChoiceField(choices=[('approve', 'Approve'), ('reject', 'Reject')])
    note = forms.CharField(max_length=255, required=False)
