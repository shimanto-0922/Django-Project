from django.contrib import admin

from .models import Amenity, Property, PropertyImage, Utility


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


class UtilityInline(admin.TabularInline):
    model = Utility
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'landlord', 'location', 'category', 'price', 'status', 'is_featured', 'is_available', 'created_at')
    list_filter = ('status', 'category', 'division', 'property_type', 'tenant_gender', 'is_featured', 'is_available')
    search_fields = ('title', 'location', 'address', 'landlord__username')
    filter_horizontal = ('amenities',)
    inlines = [PropertyImageInline, UtilityInline]
    actions = ['approve_selected']

    @admin.action(description='Approve selected listings')
    def approve_selected(self, request, queryset):
        updated = queryset.update(status=Property.Status.APPROVED, moderation_note='')
        self.message_user(request, f'{updated} listing(s) approved.')


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'description')
    search_fields = ('name',)


@admin.register(Utility)
class UtilityAdmin(admin.ModelAdmin):
    list_display = ('property', 'name', 'amount', 'billing_period', 'included_in_rent')
    list_filter = ('name', 'billing_period')
