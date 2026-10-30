from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import LandlordProfile, TenantProfile, User


@admin.register(User)
class GhorifyUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    fieldsets = UserAdmin.fieldsets + (
        ('Ghorify', {'fields': ('role', 'phone', 'avatar', 'bio')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Ghorify', {'fields': ('email', 'role', 'phone')}),
    )


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_location', 'occupation', 'monthly_budget')
    search_fields = ('user__username', 'preferred_location')


@admin.register(LandlordProfile)
class LandlordProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nid_number', 'status', 'verified_by', 'verified_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'nid_number')
