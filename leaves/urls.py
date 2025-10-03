from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('apply/', views.application_create_view, name='application_create'),
]