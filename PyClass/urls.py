from django.contrib import admin
from django.urls import path

from . import views
app_name = 'pyclass'
urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('login', views.loginpage, name='login'),
    path('register', views.register, name='register')
]