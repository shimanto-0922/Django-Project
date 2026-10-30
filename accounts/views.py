from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LandlordProfileForm, LoginForm, RegisterForm, TenantProfileForm, UserUpdateForm
from .models import LandlordProfile


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome to Ghorify, {user.first_name}! Your account is ready.')
        if user.is_landlord:
            messages.info(request, 'Upload your verification documents so tenants can trust your listings.')
            return redirect('accounts:profile')
        return redirect('dashboard:home')
    return render(request, 'accounts/register.html', {'form': form})


class GhorifyLoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def profile(request):
    user = request.user
    role_form_class, role_instance = None, None
    if user.is_tenant:
        role_form_class, role_instance = TenantProfileForm, user.tenant_profile
    elif user.is_landlord:
        role_form_class, role_instance = LandlordProfileForm, user.landlord_profile

    user_form = UserUpdateForm(request.POST or None, request.FILES or None, instance=user)
    role_form = role_form_class(request.POST or None, request.FILES or None, instance=role_instance) if role_form_class else None

    if request.method == 'POST':
        forms_valid = user_form.is_valid() and (role_form is None or role_form.is_valid())
        if forms_valid:
            user_form.save()
            if role_form:
                profile_obj = role_form.save(commit=False)
                # A new document upload sends the landlord back into the review queue.
                if user.is_landlord and 'verification_docs' in role_form.changed_data and profile_obj.verification_docs:
                    profile_obj.status = LandlordProfile.Status.PENDING
                    profile_obj.review_note = ''
                    messages.info(request, 'Documents submitted. An admin will review them shortly.')
                profile_obj.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('accounts:profile')
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'accounts/profile.html', {'user_form': user_form, 'role_form': role_form})
