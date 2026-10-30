from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import LandlordProfile, TenantProfile, User


def validate_file_size(uploaded):
    if uploaded and hasattr(uploaded, 'size') and uploaded.size > settings.MAX_UPLOAD_SIZE:
        raise forms.ValidationError('File is too large. Maximum size is 5 MB.')
    return uploaded


class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[(User.Role.TENANT, 'I am looking for a home'), (User.Role.LANDLORD, 'I want to rent out my property')],
        widget=forms.RadioSelect,
        initial=User.Role.TENANT,
    )
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ('role', 'first_name', 'last_name', 'username', 'email', 'phone')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Username or email')

    def clean(self):
        # Allow logging in with the email address as well as the username.
        identifier = self.cleaned_data.get('username', '')
        if '@' in identifier:
            match = User.objects.filter(email__iexact=identifier).first()
            if match:
                self.cleaned_data['username'] = match.username
        return super().clean()


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'avatar', 'bio')
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email

    def clean_avatar(self):
        return validate_file_size(self.cleaned_data.get('avatar'))


class TenantProfileForm(forms.ModelForm):
    class Meta:
        model = TenantProfile
        fields = ('preferred_location', 'occupation', 'family_size', 'monthly_budget')


class LandlordProfileForm(forms.ModelForm):
    class Meta:
        model = LandlordProfile
        fields = ('nid_number', 'verification_docs')

    def clean_verification_docs(self):
        doc = validate_file_size(self.cleaned_data.get('verification_docs'))
        if doc and hasattr(doc, 'name'):
            ext = doc.name.rsplit('.', 1)[-1].lower()
            if ext not in ('pdf', 'jpg', 'jpeg', 'png'):
                raise forms.ValidationError('Only PDF, JPG or PNG files are accepted.')
        return doc
