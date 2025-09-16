from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    path('webhook/', views.webhook_handler, name='webhook_handler'),
]
