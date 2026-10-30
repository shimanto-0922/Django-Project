from django.urls import path

from . import views

app_name = 'search'

urlpatterns = [
    path('', views.search, name='search'),
    path('save/', views.save_search, name='save'),
    path('saved/', views.saved_list, name='saved'),
    path('saved/new/', views.saved_create, name='saved_create'),
    path('saved/<int:pk>/edit/', views.saved_update, name='saved_update'),
    path('saved/<int:pk>/delete/', views.saved_delete, name='saved_delete'),
    path('saved/<int:pk>/run/', views.saved_run, name='saved_run'),
]
