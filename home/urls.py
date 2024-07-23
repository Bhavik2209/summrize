# urls.py
from django.urls import path
from home import views

urlpatterns = [
    path('', views.index, name='index'),
    path('ask_question/', views.ask_question, name='ask_question'),
]
