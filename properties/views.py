from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import landlord_required
from interactions.forms import RentalRequestForm, ReviewForm, VisitRequestForm
from interactions.services import tenant_context_for_property

from .forms import BrowseFilterForm, PropertyForm, PropertyImageForm, UtilityForm
from .models import CATEGORY_META, Property, PropertyImage, Utility


AREA_FALLBACK_PHOTOS = ['building_1', 'building_2', 'building_3', 'building_4', 'house_1', 'house_2']


def _listing_qs():
    return (Property.objects.visible()
            .select_related('landlord__landlord_profile')
            .prefetch_related('images').with_ratings())


def _category_counts(qs):
    counts = dict(qs.order_by().values_list('category').annotate(n=Count('id')))
    return [{'key': key, 'label': label, 'icon': CATEGORY_META[key][0], 'blurb': CATEGORY_META[key][1],
             'count': counts.get(key, 0)} for key, label in Property.Category.choices]


def _popular_areas(qs, limit=8):
    rows = qs.order_by().values('location', 'city').annotate(n=Count('id')).order_by('-n', 'location')[:limit]
    areas = []
    for i, row in enumerate(rows):
        cover = (PropertyImage.objects.filter(property__in=qs.filter(location=row['location']), is_primary=True)
                 .order_by('-property__is_featured').first())
        areas.append({**row, 'image': cover.image.url if cover else None,
                      'fallback': AREA_FALLBACK_PHOTOS[i % len(AREA_FALLBACK_PHOTOS)]})
    return areas


def home(request):
    visible = _listing_qs()
    context = {
        'featured': visible.filter(is_featured=True).order_by('-updated_at')[:6],
        'latest': visible.order_by('-created_at')[:8],
        'categories': _category_counts(visible),
        'areas': _popular_areas(visible),
        'stats': {
            'listings': visible.count(),
            'areas': visible.order_by().values('location').distinct().count(),
            'landlords': visible.order_by().values('landlord').distinct().count(),
        },
    }
    return render(request, 'properties/home.html', context)


def browse(request):
    form = BrowseFilterForm(request.GET or None)
    base = _listing_qs()
    qs = form.apply(base) if form.is_valid() else base.order_by('-is_featured', '-created_at')

    page = Paginator(qs, 12).get_page(request.GET.get('page'))
    query_string = request.GET.copy()
    query_string.pop('page', None)
    active_category = request.GET.get('category', '')
    return render(request, 'properties/browse.html', {
        'form': form, 'page': page, 'query_string': query_string.urlencode(),
        'categories': _category_counts(base),
        'divisions': dict(base.order_by().values_list('division').annotate(n=Count('id'))),
        'active_category': active_category,
        'active_category_label': dict(Property.Category.choices).get(active_category),
    })


def detail(request, pk):
    prop = get_object_or_404(
        Property.objects.select_related('landlord', 'landlord__landlord_profile')
        .prefetch_related('images', 'utilities', 'amenities', 'reviews__tenant'),
        pk=pk,
    )
    user = request.user
    is_owner = prop.is_owned_by(user)
    is_admin = user.is_authenticated and user.is_platform_admin
    if not prop.is_published and not (is_owner or is_admin):
        raise Http404('This listing is not available.')

    if not is_owner:
        Property.objects.filter(pk=prop.pk).update(view_count=F('view_count') + 1)

    similar = (_listing_qs().filter(Q(location__iexact=prop.location) | Q(category=prop.category))
               .exclude(pk=prop.pk).order_by('-is_featured', '-created_at')[:4])

    context = {
        'property': prop,
        'is_owner': is_owner,
        'reviews': prop.reviews.all(),
        'similar': similar,
        'visit_form': VisitRequestForm(),
        'rental_form': RentalRequestForm(),
        'review_form': ReviewForm(),
    }
    context.update(tenant_context_for_property(user, prop))
    return render(request, 'properties/detail.html', context)


# ---------------------------------------------------------------------------
# Landlord: property CRUD
# ---------------------------------------------------------------------------

def _owned_property(request, pk):
    return get_object_or_404(Property, pk=pk, landlord=request.user)


@landlord_required
def my_properties(request):
    properties = (request.user.properties.prefetch_related('images')
                  .with_ratings().order_by('-created_at'))
    status = request.GET.get('status')
    if status in Property.Status.values:
        properties = properties.filter(status=status)
    return render(request, 'properties/my_properties.html', {'properties': properties, 'active_status': status})


@landlord_required
def property_create(request):
    form = PropertyForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        prop = form.save(commit=False)
        prop.landlord = request.user
        prop.status = Property.Status.PENDING
        prop.save()
        form.save_m2m()
        for index, photo in enumerate(form.cleaned_data['photos']):
            PropertyImage.objects.create(property=prop, image=photo, is_primary=(index == 0))
        messages.success(request, 'Listing created. It will be visible to tenants after admin approval.')
        return redirect('properties:utilities', pk=prop.pk)
    return render(request, 'properties/property_form.html', {'form': form, 'is_edit': False})


@landlord_required
def property_update(request, pk):
    prop = _owned_property(request, pk)
    form = PropertyForm(request.POST or None, request.FILES or None, instance=prop)
    if request.method == 'POST' and form.is_valid():
        prop = form.save(commit=False)
        if prop.status == Property.Status.REJECTED:
            prop.status = Property.Status.PENDING
            prop.moderation_note = ''
            messages.info(request, 'Your changes were sent back to the admin for another review.')
        prop.save()
        form.save_m2m()
        has_primary = prop.images.filter(is_primary=True).exists()
        for index, photo in enumerate(form.cleaned_data['photos']):
            PropertyImage.objects.create(property=prop, image=photo, is_primary=(not has_primary and index == 0))
        messages.success(request, 'Listing updated.')
        return redirect(prop.get_absolute_url())
    return render(request, 'properties/property_form.html', {'form': form, 'is_edit': True, 'property': prop})


@landlord_required
def property_delete(request, pk):
    prop = _owned_property(request, pk)
    if request.method == 'POST':
        for image in prop.images.all():
            image.delete()  # also removes the file from disk
        title = prop.title
        prop.delete()
        messages.success(request, f'"{title}" has been deleted.')
        return redirect('properties:mine')
    return render(request, 'properties/property_confirm_delete.html', {'property': prop})


@landlord_required
@require_POST
def toggle_availability(request, pk):
    prop = _owned_property(request, pk)
    prop.is_available = not prop.is_available
    prop.save(update_fields=['is_available', 'updated_at'])
    state = 'available' if prop.is_available else 'marked as rented'
    messages.success(request, f'"{prop.title}" is now {state}.')
    return redirect(request.POST.get('next') or 'properties:mine')


# ---------------------------------------------------------------------------
# Landlord: photo management (media CRUD)
# ---------------------------------------------------------------------------

@landlord_required
def manage_images(request, pk):
    prop = _owned_property(request, pk)
    form = PropertyImageForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        image = form.save(commit=False)
        image.property = prop
        if not prop.images.exists():
            image.is_primary = True
        image.save()
        messages.success(request, 'Photo uploaded.')
        return redirect('properties:images', pk=prop.pk)
    return render(request, 'properties/manage_images.html', {'property': prop, 'form': form, 'images': prop.images.all()})


@landlord_required
def image_update(request, pk, image_id):
    prop = _owned_property(request, pk)
    image = get_object_or_404(PropertyImage, pk=image_id, property=prop)
    form = PropertyImageForm(request.POST or None, request.FILES or None, instance=image)
    if request.method == 'POST' and form.is_valid():
        old_file = image.image.name if 'image' in form.changed_data else None
        storage = image.image.storage
        form.save()
        if old_file:
            storage.delete(old_file)
        messages.success(request, 'Photo updated.')
        return redirect('properties:images', pk=prop.pk)
    return render(request, 'properties/image_form.html', {'property': prop, 'form': form, 'image': image})


@landlord_required
@require_POST
def image_delete(request, pk, image_id):
    prop = _owned_property(request, pk)
    image = get_object_or_404(PropertyImage, pk=image_id, property=prop)
    was_primary = image.is_primary
    image.delete()
    if was_primary:
        next_image = prop.images.first()
        if next_image:
            next_image.is_primary = True
            next_image.save()
    messages.success(request, 'Photo deleted.')
    return redirect('properties:images', pk=prop.pk)


@landlord_required
@require_POST
def image_make_primary(request, pk, image_id):
    prop = _owned_property(request, pk)
    image = get_object_or_404(PropertyImage, pk=image_id, property=prop)
    image.is_primary = True
    image.save()
    messages.success(request, 'Cover photo changed.')
    return redirect('properties:images', pk=prop.pk)


# ---------------------------------------------------------------------------
# Landlord: utility bills (used for the monthly cost estimate)
# ---------------------------------------------------------------------------

@landlord_required
def manage_utilities(request, pk):
    prop = _owned_property(request, pk)
    form = UtilityForm(request.POST or None, property_obj=prop)
    if request.method == 'POST' and form.is_valid():
        utility = form.save(commit=False)
        utility.property = prop
        utility.save()
        messages.success(request, f'{utility.get_name_display()} added.')
        return redirect('properties:utilities', pk=prop.pk)
    return render(request, 'properties/manage_utilities.html', {
        'property': prop, 'form': form, 'utilities': prop.utilities.all(),
    })


@landlord_required
def utility_update(request, pk, utility_id):
    prop = _owned_property(request, pk)
    utility = get_object_or_404(Utility, pk=utility_id, property=prop)
    form = UtilityForm(request.POST or None, instance=utility, property_obj=prop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Utility updated.')
        return redirect('properties:utilities', pk=prop.pk)
    return render(request, 'properties/utility_form.html', {'property': prop, 'form': form, 'utility': utility})


@landlord_required
@require_POST
def utility_delete(request, pk, utility_id):
    prop = _owned_property(request, pk)
    utility = get_object_or_404(Utility, pk=utility_id, property=prop)
    utility.delete()
    messages.success(request, 'Utility removed.')
    return redirect('properties:utilities', pk=prop.pk)
