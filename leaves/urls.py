from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('apply/', views.application_create_view, name='application_create'),
    path('approvals/', views.approval_task_list_view, name='approval_list'),
    path('application/<int:pk>/', views.application_detail_view, name='application_detail'),
]