from django.urls import path

from . import views

app_name = 'interactions'

urlpatterns = [
    path('favourites/', views.favourite_list, name='favourites'),
    path('favourites/<int:pk>/toggle/', views.favourite_toggle, name='favourite_toggle'),

    path('compare/', views.comparison_detail, name='compare'),
    path('compare/new/', views.comparison_create, name='comparison_create'),
    path('compare/<int:pk>/', views.comparison_detail, name='comparison'),
    path('compare/<int:pk>/rename/', views.comparison_rename, name='comparison_rename'),
    path('compare/<int:pk>/activate/', views.comparison_activate, name='comparison_activate'),
    path('compare/<int:pk>/delete/', views.comparison_delete, name='comparison_delete'),
    path('compare/add/<int:pk>/', views.comparison_add, name='comparison_add'),
    path('compare/item/<int:item_id>/remove/', views.comparison_remove, name='comparison_remove'),

    path('visits/', views.visit_list, name='visits'),
    path('visits/request/<int:pk>/', views.visit_create, name='visit_create'),
    path('visits/<int:visit_id>/edit/', views.visit_update, name='visit_update'),
    path('visits/<int:visit_id>/cancel/', views.visit_cancel, name='visit_cancel'),

    path('rentals/', views.rental_list, name='rentals'),
    path('rentals/apply/<int:pk>/', views.rental_create, name='rental_create'),
    path('rentals/<int:rental_id>/cancel/', views.rental_cancel, name='rental_cancel'),

    path('reviews/', views.review_list, name='reviews'),
    path('reviews/write/<int:pk>/', views.review_create, name='review_create'),
    path('reviews/<int:review_id>/edit/', views.review_update, name='review_update'),
    path('reviews/<int:review_id>/delete/', views.review_delete, name='review_delete'),

    path('report/<int:pk>/', views.report_create, name='report_create'),

    path('landlord/requests/', views.incoming_requests, name='incoming'),
    path('landlord/visits/<int:visit_id>/respond/', views.respond_visit, name='respond_visit'),
    path('landlord/rentals/<int:rental_id>/respond/', views.respond_rental, name='respond_rental'),
]
