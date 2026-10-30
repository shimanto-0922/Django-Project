from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', views.admin_overview, name='admin'),
    path('admin/listings/', views.moderation_queue, name='moderation'),
    path('admin/listings/<int:pk>/moderate/', views.moderate_property, name='moderate'),
    path('admin/listings/<int:pk>/feature/', views.toggle_featured, name='toggle_featured'),
    path('admin/landlords/',views.landlord_verification, name='landlords'),
    path('admin/landlords/<int:pk>/verify/', views.verify_landlord, name='verify_landlord'),
    path('admin/reports/', views.report_queue, name='reports'),
    path('admin/reports/<int:pk>/handle/', views.handle_report, name='handle_report'),
    path('admin/users/', views.user_list, name='users'),
    path('admin/users/<int:pk>/toggle/', views.toggle_user_active, name='toggle_user'),
]
