from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    """Allow the view only for logged-in users whose role is in `roles`.

    Platform admins (role=admin or superuser) are accepted when 'admin' is listed.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            allowed = user.role in roles or ('admin' in roles and user.is_superuser)
            if not allowed:
                messages.error(request, 'You do not have permission to open that page.')
                return redirect('dashboard:home')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


tenant_required = role_required('tenant')
landlord_required = role_required('landlord')
admin_required = role_required('admin')
