"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# management_system/urls.py

from django.contrib import admin
from django.urls import path, include 
from django.conf import settings 
from django.views.generic import RedirectView

from leaves import views as leaves_views 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('leaves/', include('leaves.urls')), # leavesアプリのURLをインクルード
    path('', RedirectView.as_view(pattern_name='leaves:dashboard'), name='home'),
]

# DEBUGモードがTrueの場合のみ、開発用のログインURLを追加
if settings.DEBUG:
    urlpatterns += [
        path('dev-login/', leaves_views.dev_login_view, name='dev_login'),
        path('logout/', leaves_views.logout_view, name='logout'),
    ]
