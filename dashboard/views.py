from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from accounts.models import LandlordProfile, User
from interactions.models import RentalRequest, Report, RequestStatus, VisitRequest
from properties.models import Property
from search.matching import MatchEngine


@login_required
def home(request):
    user = request.user
    if user.is_platform_admin:
        return admin_overview(request)
    if user.is_landlord:
        return landlord_dashboard(request)
    return tenant_dashboard(request)


def _recommendations(user, limit=3):
    """Use the newest saved search, otherwise the tenant profile, to suggest homes."""
    saved = user.search_criteria.first()
    if saved:
        prefs, source = saved.as_preferences(), f'your saved search "{saved.name}"'
    else:
        profile = user.tenant_profile
        prefs = {'location': profile.preferred_location, 'max_price': profile.monthly_budget}
        source = 'your profile preferences'
    if not any(prefs.values()):
        return [], None
    candidates = Property.objects.visible().prefetch_related('images', 'amenities', 'utilities')
    return MatchEngine(prefs).smart_match(candidates)[:limit], source


def tenant_dashboard(request):
    user = request.user
    recommendations, source = _recommendations(user)
    upcoming = (user.visit_requests.filter(status=RequestStatus.APPROVED, preferred_date__gte=timezone.localdate())
                .select_related('property').order_by('preferred_date')[:4])
    context = {
        'stats': {
            'favourites': user.favourites.count(),
            'visits': user.visit_requests.filter(status__in=[RequestStatus.PENDING, RequestStatus.APPROVED]).count(),
            'rentals': user.rental_requests.filter(status=RequestStatus.PENDING).count(),
            'saved': user.search_criteria.count(),
        },
        'recommendations': recommendations,
        'recommendation_source': source,
        'upcoming_visits': upcoming,
        'recent_rentals': user.rental_requests.select_related('property')[:4],
    }
    return render(request, 'dashboard/tenant.html', context)


def landlord_dashboard(request):
    user = request.user
    props = user.properties.all()
    pending_visits = VisitRequest.objects.filter(property__landlord=user, status=RequestStatus.PENDING)
    pending_rentals = RentalRequest.objects.filter(property__landlord=user, status=RequestStatus.PENDING)
    context = {
        'profile': user.landlord_profile,
        'stats': {
            'listings': props.count(),
            'published': props.filter(status=Property.Status.APPROVED).count(),
            'views': props.aggregate(total=Sum('view_count'))['total'] or 0,
            'requests': pending_visits.count() + pending_rentals.count(),
        },
        'top_properties': props.prefetch_related('images').annotate(
            fav_count=Count('favourited_by', distinct=True)).order_by('-view_count')[:5],
        'pending_visits': pending_visits.select_related('property', 'tenant')[:5],
        'pending_rentals': pending_rentals.select_related('property', 'tenant')[:5],
        'needs_attention': props.filter(status=Property.Status.REJECTED),
    }
    return render(request, 'dashboard/landlord.html', context)


# ---------------------------------------------------------------------------
# Platform admin
# ---------------------------------------------------------------------------

@admin_required
def admin_overview(request):
    context = {
        'stats': {
            'users': User.objects.count(),
            'tenants': User.objects.filter(role=User.Role.TENANT).count(),
            'landlords': User.objects.filter(role=User.Role.LANDLORD).count(),
            'published': Property.objects.approved().count(),
            'pending_properties': Property.objects.filter(status=Property.Status.PENDING).count(),
            'pending_landlords': LandlordProfile.objects.filter(status=LandlordProfile.Status.PENDING).count(),
            'open_reports': Report.objects.filter(status=Report.Status.OPEN).count(),
            'rentals_done': RentalRequest.objects.filter(status=RequestStatus.APPROVED).count(),
        },
        'area_breakdown': (Property.objects.approved().values('location')
                           .annotate(n=Count('id')).order_by('-n')[:6]),
        'latest_pending': Property.objects.filter(status=Property.Status.PENDING)
        .select_related('landlord', 'landlord__landlord_profile')[:5],
        'latest_reports': Report.objects.filter(status=Report.Status.OPEN).select_related('property', 'reporter')[:5],
    }
    return render(request, 'dashboard/admin_overview.html', context)


@admin_required
def moderation_queue(request):
    status = request.GET.get('status', Property.Status.PENDING)
    qs = (Property.objects.select_related('landlord', 'landlord__landlord_profile')
          .prefetch_related('images').annotate(open_reports=Count('reports', filter=Q(reports__status='open')))
          .order_by('-created_at'))
    if status in Property.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 12).get_page(request.GET.get('page'))
    return render(request, 'dashboard/moderation.html', {
        'page': page, 'status': status, 'status_choices': Property.Status.choices,
    })


@admin_required
@require_POST
def moderate_property(request, pk):
    prop = get_object_or_404(Property.objects.select_related('landlord__landlord_profile'), pk=pk)
    decision = request.POST.get('decision')
    note = request.POST.get('note', '').strip()[:255]
    if decision == 'approve':
        if not prop.landlord.landlord_profile.is_verified:
            messages.error(request, f'Verify the landlord "{prop.landlord}" before publishing their listing.')
            return redirect(request.POST.get('next') or 'dashboard:moderation')
        prop.status, prop.moderation_note = Property.Status.APPROVED, ''
        messages.success(request, f'"{prop.title}" is now live.')
    elif decision == 'reject':
        if not note:
            messages.error(request, 'Please write a short reason so the landlord can fix the listing.')
            return redirect(request.POST.get('next') or 'dashboard:moderation')
        prop.status, prop.moderation_note = Property.Status.REJECTED, note
        messages.info(request, f'"{prop.title}" was rejected.')
    prop.save(update_fields=['status', 'moderation_note', 'updated_at'])
    return redirect(request.POST.get('next') or 'dashboard:moderation')


@admin_required
@require_POST
def toggle_featured(request, pk):
    prop = get_object_or_404(Property, pk=pk, status=Property.Status.APPROVED)
    prop.is_featured = not prop.is_featured
    prop.save(update_fields=['is_featured', 'updated_at'])
    messages.success(request, f'"{prop.title}" is {"now featured" if prop.is_featured else "no longer featured"}.')
    return redirect(request.POST.get('next') or 'dashboard:moderation')


@admin_required
def landlord_verification(request):
    status = request.GET.get('status', LandlordProfile.Status.PENDING)
    profiles = LandlordProfile.objects.select_related('user', 'verified_by').annotate(listings=Count('user__properties'))
    if status in LandlordProfile.Status.values:
        profiles = profiles.filter(status=status)
    return render(request, 'dashboard/landlords.html', {
        'profiles': profiles, 'status': status, 'status_choices': LandlordProfile.Status.choices,
    })


@admin_required
@require_POST
def verify_landlord(request, pk):
    profile = get_object_or_404(LandlordProfile, pk=pk)
    if request.POST.get('decision') == 'approve':
        if not profile.verification_docs:
            messages.error(request, 'This landlord has not uploaded any documents yet.')
        else:
            profile.mark_verified(request.user)
            messages.success(request, f'{profile.user} is now a verified landlord.')
    else:
        profile.mark_rejected(request.user, request.POST.get('note', '').strip()[:255])
        messages.info(request, f'Verification for {profile.user} was rejected.')
    return redirect(request.POST.get('next') or 'dashboard:landlords')


@admin_required
def report_queue(request):
    status = request.GET.get('status', Report.Status.OPEN)
    reports = Report.objects.select_related('property', 'reporter', 'handled_by')
    if status in Report.Status.values:
        reports = reports.filter(status=status)
    return render(request, 'dashboard/reports.html', {
        'reports': reports, 'status': status, 'status_choices': Report.Status.choices,
    })


@admin_required
@require_POST
def handle_report(request, pk):
    report = get_object_or_404(Report.objects.select_related('property'), pk=pk)
    action = request.POST.get('action')
    report.admin_note = request.POST.get('note', '').strip()[:255]
    report.handled_by = request.user
    if action == 'unpublish':
        prop = report.property
        prop.status = Property.Status.REJECTED
        prop.moderation_note = f'Unpublished after a report: {report.get_reason_display()}. {report.admin_note}'.strip()[:255]
        prop.save(update_fields=['status', 'moderation_note', 'updated_at'])
        report.status = Report.Status.RESOLVED
        # Other open reports on the same listing are settled by the same action.
        Report.objects.filter(property=prop, status=Report.Status.OPEN).exclude(pk=report.pk).update(
            status=Report.Status.RESOLVED, handled_by=request.user, admin_note='Listing unpublished.')
        messages.success(request, f'"{prop.title}" was unpublished.')
    else:
        report.status = Report.Status.DISMISSED
        messages.info(request, 'Report dismissed.')
    report.save()
    return redirect(request.POST.get('next') or 'dashboard:reports')


@admin_required
def user_list(request):
    role = request.GET.get('role', '')
    q = request.GET.get('q', '').strip()
    users = User.objects.annotate(listing_count=Count('properties')).order_by('-date_joined')
    if role in User.Role.values:
        users = users.filter(role=role)
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q) |
                             Q(first_name__icontains=q) | Q(last_name__icontains=q))
    page = Paginator(users, 15).get_page(request.GET.get('page'))
    return render(request, 'dashboard/users.html', {'page': page, 'role': role, 'q': q, 'roles': User.Role.choices})


@admin_required
@require_POST
def toggle_user_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user or target.is_superuser:
        messages.error(request, 'You cannot deactivate this account.')
    else:
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        messages.success(request, f'{target} has been {"activated" if target.is_active else "deactivated"}.')
    return redirect(request.POST.get('next') or 'dashboard:users')
