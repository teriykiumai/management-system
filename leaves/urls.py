from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('apply/', views.application_create_view, name='application_create'),
    path('history/', views.application_history_view, name='application_history'),
    path('approvals/', views.approval_task_list_view, name='approval_list'),
    path('application/<int:pk>/', views.application_detail_view, name='application_detail'),
    path('application/<int:pk>/cancel/', views.request_cancellation_view, name='request_cancellation'),
]