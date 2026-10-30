from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import landlord_required, tenant_required
from properties.models import Property

from .forms import (ComparisonForm, LandlordResponseForm, RentalRequestForm, ReportForm, ReviewForm,
                    VisitRequestForm)
from .models import (ACTIVE_STATUSES, Comparison, ComparisonItem, Favourite, RentalRequest, Report,
                     RequestStatus, Review, VisitRequest)
from .services import active_comparison, can_review, respond_to_rental, respond_to_visit


def _visible_property(pk):
    return get_object_or_404(Property.objects.approved(), pk=pk)


def _form_page(request, title, form, prop, submit_label, subtitle=''):
    """Fallback page used when a form posted from the property page has errors."""
    return render(request, 'interactions/form_page.html', {
        'title': title, 'subtitle': subtitle, 'form': form, 'property': prop, 'submit_label': submit_label,
    })


# ---------------------------------------------------------------------------
# Favourites
# ---------------------------------------------------------------------------

@tenant_required
@require_POST
def favourite_toggle(request, pk):
    prop = _visible_property(pk)
    favourite, created = Favourite.objects.get_or_create(tenant=request.user, property=prop)
    if created:
        messages.success(request, f'Saved "{prop.title}" to your favourites.')
    else:
        favourite.delete()
        messages.info(request, f'Removed "{prop.title}" from your favourites.')
    return redirect(request.POST.get('next') or prop.get_absolute_url())


@tenant_required
def favourite_list(request):
    favourites = (request.user.favourites.select_related('property')
                  .prefetch_related('property__images', 'property__utilities'))
    return render(request, 'interactions/favourites.html', {'favourites': favourites})


# ---------------------------------------------------------------------------
# Comparison (max 3 properties side by side)
# ---------------------------------------------------------------------------

def _comparison_rows(props):
    """Rows for the comparison table. The best value of each row is highlighted."""

    def best(values, pick):
        clean = [v for v in values if v is not None]
        if len(clean) < 2:
            return None
        target = pick(clean)
        return values.index(target) if clean.count(target) == 1 else None

    def row(label, values, display=None, pick=None):
        return {'label': label, 'values': display or values, 'best': best(values, pick) if pick else None}

    rents = [p.price for p in props]
    totals = [p.monthly_cost for p in props]
    sizes = [p.size for p in props]
    ratings = [p.average_rating for p in props]
    amenity_counts = [p.amenities.count() for p in props]
    return [
        row('Monthly rent', rents, [f'৳ {v:,}' for v in rents], min),
        row('Estimated total / month', totals, [f'৳ {v:,.0f}' for v in totals], min),
        row('Advance', [p.advance_amount for p in props], [f'৳ {p.advance_amount:,}' for p in props], min),
        row('Area', [p.location for p in props]),
        row('Type', [p.get_property_type_display() for p in props]),
        row('Category', [p.get_category_display() for p in props]),
        row('Bedrooms', [p.bedrooms for p in props], pick=max),
        row('Bathrooms', [p.bathrooms for p in props], pick=max),
        row('Size (sq ft)', sizes, [s or '-' for s in sizes], max),
        row('Floor', [p.floor_label for p in props]),
        row('Furnished', [p.furnished for p in props]),
        row('Parking', [p.parking for p in props]),
        row('Pet friendly', [p.pet_friendly for p in props]),
        row('Amenities', amenity_counts, [f'{c} listed' for c in amenity_counts], max),
        row('Rating', ratings, [f'{r} ★' if r else 'No reviews' for r in ratings], max),
    ]


@tenant_required
def comparison_detail(request, pk=None):
    if pk is None:
        comparison = active_comparison(request.user, create=True)
    else:
        comparison = get_object_or_404(Comparison, pk=pk, tenant=request.user)
    items = list(comparison.items.select_related('property').prefetch_related(
        'property__images', 'property__utilities', 'property__amenities', 'property__reviews'))
    props = [item.property for item in items]
    return render(request, 'interactions/comparison_detail.html', {
        'comparison': comparison,
        'items': items,
        'rows': _comparison_rows(props) if props else [],
        'others': request.user.comparisons.exclude(pk=comparison.pk).annotate(n=Count('items')),
        'rename_form': ComparisonForm(instance=comparison),
    })


@tenant_required
@require_POST
def comparison_add(request, pk):
    prop = _visible_property(pk)
    comparison = active_comparison(request.user, create=True)
    ok, msg = comparison.add(prop)
    (messages.success if ok else messages.warning)(request, msg)
    return redirect(request.POST.get('next') or prop.get_absolute_url())


@tenant_required
@require_POST
def comparison_remove(request, item_id):
    item = get_object_or_404(ComparisonItem, pk=item_id, comparison__tenant=request.user)
    comparison = item.comparison
    item.delete()
    comparison.save(update_fields=['updated_at'])
    messages.info(request, 'Property removed from the comparison.')
    return redirect('interactions:comparison', pk=comparison.pk)


@tenant_required
@require_POST
def comparison_create(request):
    form = ComparisonForm(request.POST)
    comparison = form.save(commit=False) if form.is_valid() else Comparison(name='My comparison')
    comparison.tenant = request.user
    comparison.save()
    messages.success(request, f'"{comparison.name}" created. New properties will be added here.')
    return redirect('interactions:comparison', pk=comparison.pk)


@tenant_required
@require_POST
def comparison_rename(request, pk):
    comparison = get_object_or_404(Comparison, pk=pk, tenant=request.user)
    form = ComparisonForm(request.POST, instance=comparison)
    if form.is_valid():
        form.save()
        messages.success(request, 'Comparison renamed.')
    return redirect('interactions:comparison', pk=comparison.pk)


@tenant_required
@require_POST
def comparison_activate(request, pk):
    comparison = get_object_or_404(Comparison, pk=pk, tenant=request.user)
    comparison.save(update_fields=['updated_at'])  # most recently updated = active
    messages.info(request, f'"{comparison.name}" is now your active comparison.')
    return redirect('interactions:comparison', pk=comparison.pk)


@tenant_required
@require_POST
def comparison_delete(request, pk):
    comparison = get_object_or_404(Comparison, pk=pk, tenant=request.user)
    comparison.delete()
    messages.success(request, f'"{comparison.name}" deleted.')
    return redirect('interactions:compare')


# ---------------------------------------------------------------------------
# Visit requests
# ---------------------------------------------------------------------------

@tenant_required
@require_POST
def visit_create(request, pk):
    prop = _visible_property(pk)
    form = VisitRequestForm(request.POST, tenant=request.user, property_obj=prop)
    if form.is_valid():
        visit = form.save(commit=False)
        visit.tenant, visit.property = request.user, prop
        visit.save()
        messages.success(request, 'Visit requested! The landlord will confirm the date.')
        return redirect('interactions:visits')
    return _form_page(request, 'Request a visit', form, prop, 'Send visit request')


@tenant_required
def visit_list(request):
    visits = request.user.visit_requests.select_related('property').prefetch_related('property__images')
    return render(request, 'interactions/visit_list.html', {'visits': visits})


@tenant_required
def visit_update(request, visit_id):
    visit = get_object_or_404(VisitRequest, pk=visit_id, tenant=request.user, status=RequestStatus.PENDING)
    form = VisitRequestForm(request.POST or None, instance=visit, tenant=request.user, property_obj=visit.property)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Visit rescheduled.')
        return redirect('interactions:visits')
    return _form_page(request, 'Reschedule visit', form, visit.property, 'Save changes')


@tenant_required
@require_POST
def visit_cancel(request, visit_id):
    visit = get_object_or_404(VisitRequest, pk=visit_id, tenant=request.user, status__in=ACTIVE_STATUSES)
    visit.status = RequestStatus.CANCELLED
    visit.save(update_fields=['status'])
    messages.info(request, 'Visit cancelled.')
    return redirect('interactions:visits')


# ---------------------------------------------------------------------------
# Rental requests
# ---------------------------------------------------------------------------

@tenant_required
@require_POST
def rental_create(request, pk):
    prop = _visible_property(pk)
    form = RentalRequestForm(request.POST, tenant=request.user, property_obj=prop)
    if form.is_valid():
        rental = form.save(commit=False)
        rental.tenant, rental.property = request.user, prop
        rental.save()
        messages.success(request, 'Rental application sent. You can track its status here.')
        return redirect('interactions:rentals')
    return _form_page(request, 'Apply to rent', form, prop, 'Send application')


@tenant_required
def rental_list(request):
    rentals = request.user.rental_requests.select_related('property').prefetch_related('property__images')
    return render(request, 'interactions/rental_list.html', {'rentals': rentals})


@tenant_required
@require_POST
def rental_cancel(request, rental_id):
    rental = get_object_or_404(RentalRequest, pk=rental_id, tenant=request.user, status=RequestStatus.PENDING)
    rental.status = RequestStatus.CANCELLED
    rental.save(update_fields=['status'])
    messages.info(request, 'Rental application withdrawn.')
    return redirect('interactions:rentals')


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@tenant_required
@require_POST
def review_create(request, pk):
    prop = _visible_property(pk)
    if not can_review(request.user, prop):
        messages.error(request, 'You can review a property only after an approved visit or rental.')
        return redirect(prop.get_absolute_url())
    if Review.objects.filter(tenant=request.user, property=prop).exists():
        messages.warning(request, 'You have already reviewed this property. You can edit your review instead.')
        return redirect(prop.get_absolute_url())
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.tenant, review.property = request.user, prop
        review.save()
        messages.success(request, 'Thanks for sharing your experience!')
        return redirect(f'{prop.get_absolute_url()}#reviews')
    return _form_page(request, 'Write a review', form, prop, 'Publish review')


@tenant_required
def review_list(request):
    reviews = request.user.reviews.select_related('property')
    return render(request, 'interactions/review_list.html', {'reviews': reviews})


@tenant_required
def review_update(request, review_id):
    review = get_object_or_404(Review, pk=review_id, tenant=request.user)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Review updated.')
        return redirect(f'{review.property.get_absolute_url()}#reviews')
    return _form_page(request, 'Edit your review', form, review.property, 'Save review')


@tenant_required
@require_POST
def review_delete(request, review_id):
    review = get_object_or_404(Review, pk=review_id, tenant=request.user)
    prop = review.property
    review.delete()
    messages.info(request, 'Review deleted.')
    return redirect(request.POST.get('next') or prop.get_absolute_url())


# ---------------------------------------------------------------------------
# Reports (misleading listings)
# ---------------------------------------------------------------------------

@tenant_required
def report_create(request, pk):
    prop = _visible_property(pk)
    if Report.objects.filter(reporter=request.user, property=prop, status=Report.Status.OPEN).exists():
        messages.info(request, 'You have already reported this listing. Our team is looking into it.')
        return redirect(prop.get_absolute_url())
    form = ReportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        report = form.save(commit=False)
        report.reporter, report.property = request.user, prop
        report.save()
        messages.success(request, 'Report submitted. Thank you for keeping Ghorify safe.')
        return redirect(prop.get_absolute_url())
    return _form_page(request, 'Report this listing', form, prop, 'Submit report',
                      'Tell us what is misleading about this property. Reports are anonymous to the landlord.')


# ---------------------------------------------------------------------------
# Landlord: incoming requests
# ---------------------------------------------------------------------------

@landlord_required
def incoming_requests(request):
    tab = request.GET.get('tab', 'visits')
    status = request.GET.get('status', 'pending')
    status_filter = Q() if status == 'all' else Q(status=status)
    visits = (VisitRequest.objects.filter(status_filter, property__landlord=request.user)
              .select_related('property', 'tenant', 'tenant__tenant_profile').order_by('preferred_date'))
    rentals = (RentalRequest.objects.filter(status_filter, property__landlord=request.user)
               .select_related('property', 'tenant', 'tenant__tenant_profile'))
    pending_counts = {
        'visits': VisitRequest.objects.filter(property__landlord=request.user, status=RequestStatus.PENDING).count(),
        'rentals': RentalRequest.objects.filter(property__landlord=request.user, status=RequestStatus.PENDING).count(),
    }
    return render(request, 'interactions/incoming_requests.html', {
        'tab': tab, 'status': status, 'visits': visits, 'rentals': rentals, 'pending_counts': pending_counts,
        'status_choices': [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('all', 'All')],
    })


@landlord_required
@require_POST
def respond_visit(request, visit_id):
    visit = get_object_or_404(VisitRequest, pk=visit_id, property__landlord=request.user, status=RequestStatus.PENDING)
    form = LandlordResponseForm(request.POST)
    if form.is_valid():
        approve = form.cleaned_data['decision'] == 'approve'
        clash = approve and VisitRequest.objects.filter(
            property=visit.property, preferred_date=visit.preferred_date, time_slot=visit.time_slot,
            status=RequestStatus.APPROVED).exists()
        if clash:
            messages.error(request, 'You already approved another visit in this slot. Reject or ask to reschedule.')
        else:
            respond_to_visit(visit, approve, form.cleaned_data['note'])
            messages.success(request, f'Visit {"approved" if approve else "rejected"}.')
    return redirect(f"{request.POST.get('next') or '/me/landlord/requests/'}")


@landlord_required
@require_POST
def respond_rental(request, rental_id):
    rental = get_object_or_404(RentalRequest, pk=rental_id, property__landlord=request.user, status=RequestStatus.PENDING)
    form = LandlordResponseForm(request.POST)
    if form.is_valid():
        approve = form.cleaned_data['decision'] == 'approve'
        closed = respond_to_rental(rental, approve, form.cleaned_data['note'])
        if approve:
            extra = f' {closed} other pending application(s) were closed automatically.' if closed else ''
            messages.success(request, f'Rental approved and "{rental.property.title}" marked as rented.{extra}')
        else:
            messages.info(request, 'Rental application rejected.')
    return redirect(f"{request.POST.get('next') or '/me/landlord/requests/?tab=rentals'}")
