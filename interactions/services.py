"""Business rules shared by several views (and the property detail page)."""
from django.db import transaction
from django.utils import timezone

from .models import (ACTIVE_STATUSES, Comparison, Favourite, RentalRequest, Report, RequestStatus, Review,
                     VisitRequest)


def has_approved_contact(user, prop):
    """Privacy rule: a landlord's phone/email is revealed only after the landlord
    has accepted a visit or rental request from this tenant."""
    if not user.is_authenticated:
        return False
    if prop.is_owned_by(user) or user.is_platform_admin:
        return True
    return (VisitRequest.objects.filter(tenant=user, property=prop, status=RequestStatus.APPROVED).exists()
            or RentalRequest.objects.filter(tenant=user, property=prop, status=RequestStatus.APPROVED).exists())


def can_review(user, prop):
    """Only tenants who actually visited or rented the place may review it."""
    if not (user.is_authenticated and user.is_tenant):
        return False
    return (VisitRequest.objects.filter(tenant=user, property=prop, status=RequestStatus.APPROVED,
                                        preferred_date__lte=timezone.localdate()).exists()
            or RentalRequest.objects.filter(tenant=user, property=prop, status=RequestStatus.APPROVED).exists())


def active_comparison(user, create=False):
    comparison = user.comparisons.first()
    if comparison is None and create:
        comparison = Comparison.objects.create(tenant=user)
    return comparison


def tenant_context_for_property(user, prop):
    """Everything the detail page needs to know about the viewer's relationship with a property."""
    ctx = {
        'can_contact': has_approved_contact(user, prop),
        'is_tenant_viewer': user.is_authenticated and user.is_tenant,
        'is_favourite': False, 'in_compare': False, 'can_review': False,
        'my_review': None, 'active_visit': None, 'active_rental': None, 'has_reported': False,
    }
    if not ctx['is_tenant_viewer']:
        return ctx
    comparison = active_comparison(user)
    ctx.update({
        'is_favourite': Favourite.objects.filter(tenant=user, property=prop).exists(),
        'in_compare': bool(comparison and comparison.items.filter(property=prop).exists()),
        'can_review': can_review(user, prop),
        'my_review': Review.objects.filter(tenant=user, property=prop).first(),
        'active_visit': VisitRequest.objects.filter(tenant=user, property=prop, status__in=ACTIVE_STATUSES).first(),
        'active_rental': RentalRequest.objects.filter(tenant=user, property=prop, status__in=ACTIVE_STATUSES).first(),
        'has_reported': Report.objects.filter(reporter=user, property=prop, status=Report.Status.OPEN).exists(),
    })
    return ctx


def respond_to_visit(visit, approve, note=''):
    visit.status = RequestStatus.APPROVED if approve else RequestStatus.REJECTED
    visit.landlord_note = note
    visit.responded_at = timezone.now()
    visit.save()


@transaction.atomic
def respond_to_rental(rental, approve, note=''):
    """Approving one rental request rents the property out and closes the others."""
    rental.status = RequestStatus.APPROVED if approve else RequestStatus.REJECTED
    rental.landlord_note = note
    rental.responded_at = timezone.now()
    rental.save()
    if not approve:
        return 0
    prop = rental.property
    prop.is_available = False
    prop.save(update_fields=['is_available', 'updated_at'])
    others = RentalRequest.objects.filter(property=prop, status=RequestStatus.PENDING).exclude(pk=rental.pk)
    return others.update(
        status=RequestStatus.REJECTED,
        landlord_note='The property has been rented to another tenant.',
        responded_at=timezone.now(),
    )
