from django.urls import path
from core.views import (
    IngestaView, dashboard_view, login_view, logout_view,
    movimiento_recategorizar,
)
from core.hmac_echo import HmacEchoView
from core.auth_views import (
    register_view, registro_pendiente_view, verificar_email_view, reenviar_verificacion_view,
    perfil_view, onboarding_view, confirmar_secreto, rotar_secreto,
    fallidas_view, fallida_resolver,
    FintrackPasswordResetView, FintrackPasswordResetDoneView,
    FintrackPasswordResetConfirmView, FintrackPasswordResetCompleteView,
)
from core.organizacion_views import (
    organizacion_view, categoria_crear, categoria_eliminar,
    regla_crear, regla_eliminar, espacio_activar, espacio_crear,
    presupuestos_view, presupuesto_crear, metas_view, meta_crear, meta_actualizar,
)
from core.reportes_views import export_csv_view, auditoria_view

urlpatterns = [
    path('api/v1/conectores/ingesta/', IngestaView.as_view(), name='api_ingesta'),
    path('api/v1/conectores/hmac-echo/', HmacEchoView.as_view(), name='api_hmac_echo'),

    path('', dashboard_view, name='dashboard'),
    path('movimientos/<int:movimiento_id>/categoria/', movimiento_recategorizar, name='movimiento_recategorizar'),
    path('export/csv/', export_csv_view, name='export_csv'),
    path('auditoria/', auditoria_view, name='auditoria'),

    path('registro/', register_view, name='registro'),
    path('registro/pendiente/', registro_pendiente_view, name='registro_pendiente'),
    path('verificar/<uidb64>/<token>/', verificar_email_view, name='verificar_email'),
    path('reenviar-verificacion/', reenviar_verificacion_view, name='reenviar_verificacion'),

    path('password-reset/', FintrackPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', FintrackPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', FintrackPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', FintrackPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    path('perfil/', perfil_view, name='perfil'),
    path('onboarding/', onboarding_view, name='onboarding'),
    path('perfil/confirmar-secreto/', confirmar_secreto, name='confirmar_secreto'),
    path('perfil/rotar-secreto/', rotar_secreto, name='rotar_secreto'),
    path('fallidas/', fallidas_view, name='fallidas'),
    path('fallidas/<int:fallida_id>/resolver/', fallida_resolver, name='fallida_resolver'),

    path('organizacion/', organizacion_view, name='organizacion'),
    path('organizacion/categorias/crear/', categoria_crear, name='categoria_crear'),
    path('organizacion/categorias/<int:categoria_id>/eliminar/', categoria_eliminar, name='categoria_eliminar'),
    path('organizacion/reglas/crear/', regla_crear, name='regla_crear'),
    path('organizacion/reglas/<int:regla_id>/eliminar/', regla_eliminar, name='regla_eliminar'),
    path('espacios/activar/', espacio_activar, name='espacio_activar'),
    path('espacios/crear/', espacio_crear, name='espacio_crear'),

    path('presupuestos/', presupuestos_view, name='presupuestos'),
    path('presupuestos/crear/', presupuesto_crear, name='presupuesto_crear'),
    path('metas/', metas_view, name='metas'),
    path('metas/crear/', meta_crear, name='meta_crear'),
    path('metas/<int:meta_id>/actualizar/', meta_actualizar, name='meta_actualizar'),

    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
