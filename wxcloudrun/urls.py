# FamilyLedger/wxcloudrun/urls.py
# 接口路径与小程序前端约定一致：/api/login、/api/family、/api/bill
from django.urls import path

from wxcloudrun import views

urlpatterns = [
    path('', views.index),
    path('api/login', views.login),
    path('api/family', views.family_api),
    path('api/bill', views.bill_api),
]
