from django.contrib import admin

from .models import SearchCriteria


@admin.register(SearchCriteria)
class SearchCriteriaAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'location', 'category', 'max_price', 'updated_at')
    list_filter = ('category',)
    search_fields = ('name', 'tenant__username', 'location')
