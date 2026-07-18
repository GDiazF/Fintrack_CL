from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario, PerfilUsuario, Espacio, InstitucionFinanciera,
    CuentaFinanciera, Categoria, Comercio, ReglaCategoria,
    Moneda, Movimiento, Presupuesto, MetaAhorro, EventoAuditoria,
    WebhookNonce, IngestaFallida, AliasComercio,
)

@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('telefono',)}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'telefono', 'is_staff')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'api_key_id', 'email_verificado', 'secret_revelado', 'creado_en')
    list_filter = ('email_verificado', 'secret_revelado')
    readonly_fields = ('api_key_id', 'api_secret_token', 'creado_en')

@admin.register(Espacio)
class EspacioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'administrador', 'creado_en')
    filter_horizontal = ('miembros',)

@admin.register(InstitucionFinanciera)
class InstitucionFinancieraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'color_hex')
    list_filter = ('tipo',)

@admin.register(CuentaFinanciera)
class CuentaFinancieraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'espacio', 'institucion', 'identificador_conector', 'es_predeterminada')
    list_filter = ('institucion', 'es_predeterminada')

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'espacio', 'color_hex', 'icono')
    list_filter = ('espacio',)

@admin.register(Comercio)
class ComercioAdmin(admin.ModelAdmin):
    list_display = ('nombre_fantasia', 'categoria_sugerida')
    search_fields = ('nombre_fantasia',)

@admin.register(AliasComercio)
class AliasComercioAdmin(admin.ModelAdmin):
    list_display = ('texto_raw', 'comercio', 'creado_en')
    search_fields = ('texto_raw', 'comercio__nombre_fantasia')

@admin.register(ReglaCategoria)
class ReglaCategoriaAdmin(admin.ModelAdmin):
    list_display = ('patron_texto', 'categoria_destino', 'espacio')
    list_filter = ('espacio',)

@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display = ('codigo_iso', 'simbolo', 'decimales')

@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('fecha_transaccion', 'tipo', 'cuenta', 'comercio_raw', 'monto_clp', 'gmail_message_id')
    list_filter = ('tipo', 'cuenta', 'fecha_transaccion')
    search_fields = ('comercio_raw', 'raw_text', 'gmail_message_id')
    readonly_fields = ('gmail_message_id', 'creado_en')

@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('categoria', 'espacio', 'monto_limite', 'mes', 'anio')
    list_filter = ('mes', 'anio', 'espacio')

@admin.register(MetaAhorro)
class MetaAhorroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'espacio', 'monto_objetivo', 'monto_actual', 'fecha_limite')

@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('accion', 'usuario', 'espacio', 'fecha')
    list_filter = ('accion', 'fecha')
    readonly_fields = ('usuario', 'espacio', 'accion', 'detalles', 'fecha')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(WebhookNonce)
class WebhookNonceAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'nonce', 'timestamp', 'usado_en')
    list_filter = ('usado_en',)
    search_fields = ('nonce', 'perfil__api_key_id', 'perfil__user__username')
    readonly_fields = ('perfil', 'nonce', 'timestamp', 'usado_en')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(IngestaFallida)
class IngestaFallidaAdmin(admin.ModelAdmin):
    list_display = ('gmail_message_id', 'usuario', 'conector', 'motivo_error', 'resuelto', 'creado_en')
    list_filter = ('resuelto', 'conector', 'creado_en')
    search_fields = ('gmail_message_id', 'motivo_error', 'raw_text', 'usuario__username')
    readonly_fields = ('usuario', 'gmail_message_id', 'conector', 'fecha_correo', 'raw_text', 'motivo_error', 'creado_en')
    def has_add_permission(self, request):
        return False

