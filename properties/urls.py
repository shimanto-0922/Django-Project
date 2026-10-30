from django.urls import path

from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.home, name='home'),
    path('properties/', views.browse, name='browse'),
    path('properties/<int:pk>/', views.detail, name='detail'),

    path('landlord/properties/', views.my_properties, name='mine'),
    path('landlord/properties/new/', views.property_create, name='create'),
    path('landlord/properties/<int:pk>/edit/', views.property_update, name='update'),
    path('landlord/properties/<int:pk>/delete/', views.property_delete, name='delete'),
    path('landlord/properties/<int:pk>/availability/', views.toggle_availability, name='toggle_availability'),

    path('landlord/properties/<int:pk>/photos/', views.manage_images, name='images'),
    path('landlord/properties/<int:pk>/photos/<int:image_id>/edit/', views.image_update, name='image_update'),
    path('landlord/properties/<int:pk>/photos/<int:image_id>/delete/', views.image_delete, name='image_delete'),
    path('landlord/properties/<int:pk>/photos/<int:image_id>/cover/', views.image_make_primary, name='image_primary'),

    path('landlord/properties/<int:pk>/utilities/', views.manage_utilities, name='utilities'),
    path('landlord/properties/<int:pk>/utilities/<int:utility_id>/edit/', views.utility_update, name='utility_update'),
    path('landlord/properties/<int:pk>/utilities/<int:utility_id>/delete/', views.utility_delete, name='utility_delete'),
]
