def compare_count(request):
    """Number of properties in the tenant's active comparison (shown in the navbar)."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_tenant):
        return {}
    comparison = user.comparisons.first()
    return {'compare_count': comparison.items.count() if comparison else 0}
