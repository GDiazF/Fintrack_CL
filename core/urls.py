from django.urls import path
from core.views import IngestaView, dashboard_view, perfil_view, login_view, logout_view

urlpatterns = [
    # API de Ingesta (GAS Webhook)
    path('api/v1/conectores/ingesta/', IngestaView.as_view(), name='api_ingesta'),
    
    # Frontend Dashboard y Perfil
    path('', dashboard_view, name='dashboard'),
    path('perfil/', perfil_view, name='perfil'),

    # Autenticación nativa
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
