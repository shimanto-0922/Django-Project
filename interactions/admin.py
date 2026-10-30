from django.contrib import admin

from .models import Comparison, ComparisonItem, Favourite, RentalRequest, Report, Review, VisitRequest


class ComparisonItemInline(admin.TabularInline):
    model = ComparisonItem
    extra = 0


@admin.register(Comparison)
class ComparisonAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'created_at')
    inlines = [ComparisonItemInline]


@admin.register(Favourite)
class FavouriteAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'property', 'created_at')


@admin.register(VisitRequest)
class VisitRequestAdmin(admin.ModelAdmin):
    list_display = ('property', 'tenant', 'preferred_date', 'time_slot', 'status')
    list_filter = ('status', 'time_slot')


@admin.register(RentalRequest)
class RentalRequestAdmin(admin.ModelAdmin):
    list_display = ('property', 'tenant', 'move_in_date', 'duration_months', 'status')
    list_filter = ('status',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('property', 'tenant', 'rating', 'landlord_rating', 'created_at')
    list_filter = ('rating',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('property', 'reporter', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason')
