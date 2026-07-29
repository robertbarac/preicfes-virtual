from django.urls import path
from . import views

urlpatterns = [
    path('salones/', views.SalonListView.as_view(), name='salon_list'),
    path('salones/<int:pk>/', views.SalonDetailView.as_view(), name='salon_detail'),
]
