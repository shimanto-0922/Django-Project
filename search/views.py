from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import tenant_required
from properties.models import Property

from .forms import SearchCriteriaForm
from .matching import SMART_MATCH_THRESHOLD, MatchEngine
from .models import SearchCriteria


def search(request):
    """Search page. `mode=smart` ranks by match %, `mode=basic` filters strictly."""
    mode = request.GET.get('mode', 'smart')
    has_query = any(k for k in request.GET if k not in ('mode', 'page'))
    form = SearchCriteriaForm(request.GET if has_query else None, require_name=False)

    page = None
    total = 0
    if has_query and form.is_valid():
        engine = MatchEngine(form.preferences())
        candidates = Property.objects.visible().prefetch_related('images', 'amenities', 'utilities')
        results = engine.smart_match(candidates) if mode == 'smart' else engine.strict_filter(candidates)
        total = len(results)
        page = Paginator(results, 9).get_page(request.GET.get('page'))

    query_string = request.GET.copy()
    query_string.pop('page', None)
    return render(request, 'search/search.html', {
        'form': form,
        'mode': mode,
        'page': page,
        'total': total,
        'has_query': has_query,
        'threshold': SMART_MATCH_THRESHOLD,
        'query_string': query_string.urlencode(),
    })


@tenant_required
@require_POST
def save_search(request):
    form = SearchCriteriaForm(request.POST)
    if form.is_valid():
        criteria = form.save(commit=False)
        criteria.tenant = request.user
        criteria.save()
        form.save_m2m()
        messages.success(request, f'Search "{criteria.name}" saved.')
        return redirect('search:saved')
    messages.error(request, 'Give your search a name before saving it.')
    return redirect(f"{request.POST.get('next') or '/search/'}")


@tenant_required
def saved_list(request):
    criteria = request.user.search_criteria.prefetch_related('amenities')
    candidates = Property.objects.visible().prefetch_related('amenities', 'utilities')
    rows = [{'criteria': item, 'match_count': len(item.engine().smart_match(candidates))} for item in criteria]
    return render(request, 'search/saved_list.html', {'rows': rows})


@tenant_required
def saved_create(request):
    form = SearchCriteriaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        criteria = form.save(commit=False)
        criteria.tenant = request.user
        criteria.save()
        form.save_m2m()
        messages.success(request, f'Search "{criteria.name}" created.')
        return redirect('search:saved')
    return render(request, 'search/criteria_form.html', {'form': form, 'is_edit': False})


@tenant_required
def saved_update(request, pk):
    criteria = get_object_or_404(SearchCriteria, pk=pk, tenant=request.user)
    form = SearchCriteriaForm(request.POST or None, instance=criteria)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Saved search updated.')
        return redirect('search:saved')
    return render(request, 'search/criteria_form.html', {'form': form, 'is_edit': True, 'criteria': criteria})


@tenant_required
@require_POST
def saved_delete(request, pk):
    criteria = get_object_or_404(SearchCriteria, pk=pk, tenant=request.user)
    criteria.delete()
    messages.success(request, f'"{criteria.name}" deleted.')
    return redirect('search:saved')


@tenant_required
def saved_run(request, pk):
    criteria = get_object_or_404(SearchCriteria, pk=pk, tenant=request.user)
    return redirect(criteria.get_search_url())
