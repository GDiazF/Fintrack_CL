import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser

class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado (AbstractUser).
    Listo desde el día 1 para evitar migraciones críticas en producción en el futuro.
    """
    telefono = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'auth_user'


class PerfilUsuario(models.Model):
    """Extensión del perfil para almacenar credenciales únicas de API y firmas webhooks."""
    user = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='perfil')
    api_key_id = models.CharField(max_length=32, unique=True, editable=False)  # Identificador público
    api_secret_token = models.CharField(max_length=64, unique=True, editable=False)  # Secreto privado
    secret_revelado = models.BooleanField(
        default=False,
        help_text='True cuando el usuario confirmó haber guardado el secreto (ya no se muestra en claro).',
    )
    email_verificado = models.BooleanField(
        default=True,
        help_text='False tras registro hasta que confirme el enlace del correo. Usuarios existentes/admin quedan en True.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.api_key_id:
            self.api_key_id = f"ft_key_{secrets.token_hex(12)}"
        if not self.api_secret_token:
            self.api_secret_token = f"ft_secret_{secrets.token_urlsafe(32)}"
        super().save(*args, **kwargs)

    def rotar_secret(self):
        """Genera un nuevo secreto y lo deja pendiente de revelación única."""
        self.api_secret_token = f"ft_secret_{secrets.token_urlsafe(32)}"
        self.secret_revelado = False
        self.save(update_fields=['api_secret_token', 'secret_revelado'])
        return self.api_secret_token

    def confirmar_secreto_guardado(self):
        self.secret_revelado = True
        self.save(update_fields=['secret_revelado'])

    def __str__(self):
        return f"Perfil de {self.user.username}"


class Espacio(models.Model):
    """Aislamiento lógico (Multi-tenant elástico). Permite finanzas individuales o compartidas."""
    nombre = models.CharField(max_length=100)  # Ej: "Finanzas Personales", "Gastos Hogar"
    administrador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='espacios_administrados')
    miembros = models.ManyToManyField(Usuario, related_name='espacios_compartidos')
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class InstitucionFinanciera(models.Model):
    """Representación normalizada del origen de fondos (Bancos, Prepago, Efectivo)."""
    TIPO_CHOICES = [
        ('BANCO', 'Institución Bancaria Tradicional'),
        ('BILLETERA', 'Billetera Digital / Prepago'),
        ('EFECTIVO', 'Gestión de Efectivo Manual'),
        ('COOPERATIVA', 'Cooperativa de Ahorro y Crédito'),
    ]
    nombre = models.CharField(max_length=100, unique=True)  # Ej: "BancoEstado", "Tenpo", "Mercado Pago"
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='BANCO')
    logo_url = models.CharField(max_length=255, blank=True, null=True)
    color_hex = models.CharField(max_length=7, default="#CCCCCC")

    def __str__(self):
        return self.nombre


class CuentaFinanciera(models.Model):
    """Cuentas específicas vinculadas a un Espacio de trabajo."""
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='cuentas')
    institucion = models.ForeignKey(InstitucionFinanciera, on_delete=models.PROTECT, related_name='cuentas')
    nombre = models.CharField(max_length=100)  # Ej: "CuentaRUT", "Tarjeta Visa", "Efectivo Bolsillo"
    identificador_conector = models.CharField(max_length=50, blank=True, null=True) # Ej: "1234" (4 dígitos tarjeta)
    es_predeterminada = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('espacio', 'institucion', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"


class Categoria(models.Model):
    """Categorías de organización del dinero. Si espacio es null, es una categoría global del sistema."""
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, null=True, blank=True, related_name='categorias')
    nombre = models.CharField(max_length=100)
    color_hex = models.CharField(max_length=7, default="#3498DB")
    icono = models.CharField(max_length=50, default="bi-wallet")

    class Meta:
        unique_together = ('espacio', 'nombre')

    def __str__(self):
        if self.espacio:
            return f"{self.nombre} ({self.espacio.nombre})"
        return f"{self.nombre} (Global)"


class Comercio(models.Model):
    """Normaliza las cadenas de texto del retail (Ej: 'LIDER IQUIQUE' apunta a 'Líder')."""
    nombre_fantasia = models.CharField(max_length=150, unique=True)  # Ej: "Líder"
    categoria_sugerida = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.nombre_fantasia


class AliasComercio(models.Model):
    """
    Variantes crudas del banco que apuntan a un Comercio canónico.
    Ej: 'LIDER IQUIQUE' → Comercio 'Líder'.
    """
    texto_raw = models.CharField(max_length=150, unique=True)
    comercio = models.ForeignKey(Comercio, on_delete=models.CASCADE, related_name='aliases')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Aliases de comercio'

    def __str__(self):
        return f"{self.texto_raw} → {self.comercio.nombre_fantasia}"


class ReglaCategoria(models.Model):
    """Mapeo automático basado en patrones de texto personalizados por Espacio."""
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='reglas')
    patron_texto = models.CharField(max_length=100)  # Ej: "COPEC", "STARBUCKS"
    categoria_destino = models.ForeignKey(Categoria, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.patron_texto} -> {self.categoria_destino.nombre} ({self.espacio.nombre})"


class Moneda(models.Model):
    """Soporte multi-moneda completo (Evita lógica dura en los modelos)."""
    codigo_iso = models.CharField(max_length=3, unique=True)  # Ej: "CLP", "USD", "EUR", "UF"
    simbolo = models.CharField(max_length=10)  # Ej: "$", "US$", "UF"
    decimales = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.codigo_iso


class Movimiento(models.Model):
    """El núcleo financiero del sistema. Todo flujo de dinero es un Movimiento."""
    TIPO_CHOICES = [
        ('EGRESO', 'Gasto / Compra / Retiro'),
        ('INGRESO', 'Sueldo / Abono / Depósito'),
        ('TRANSFERENCIA', 'Transferencia entre Cuentas'),
        ('COMISION', 'Comisión / Interés Cobrado'),
    ]
    cuenta = models.ForeignKey(CuentaFinanciera, on_delete=models.CASCADE, related_name='movimientos')
    comercio = models.ForeignKey(Comercio, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    comercio_raw = models.CharField(max_length=255)  # Texto original extraído del correo
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    fecha_transaccion = models.DateTimeField()
    monto_original = models.DecimalField(max_digits=15, decimal_places=4)
    moneda_original = models.ForeignKey(Moneda, on_delete=models.PROTECT, related_name='movimientos_originales')
    monto_clp = models.IntegerField()  # Monto normalizado para reportes unificados locales
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000)  # Auditoría cambiaria
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='EGRESO')
    raw_text = models.TextField(blank=True, null=True)  # Cuerpo completo del mail para auditorías
    conector_origen = models.CharField(max_length=50, default="gmail_bancoestado_v1") # Conector versionado
    gmail_message_id = models.CharField(max_length=64, unique=True, editable=False)  # Idempotencia absoluta
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_transaccion']

    def __str__(self):
        return f"{self.tipo} - {self.cuenta.nombre} - ${self.monto_clp} ({self.fecha_transaccion.strftime('%Y-%m-%d')})"


class Presupuesto(models.Model):
    """Límites de gastos mensuales por categoría."""
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='presupuestos')
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='presupuestos')
    monto_limite = models.IntegerField()
    mes = models.PositiveIntegerField()
    anio = models.PositiveIntegerField()

    class Meta:
        unique_together = ('espacio', 'categoria', 'mes', 'anio')

    def __str__(self):
        return f"Presupuesto {self.categoria.nombre} ({self.mes}/{self.anio})"


class MetaAhorro(models.Model):
    """Objetivos financieros motivacionales."""
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='metas')
    nombre = models.CharField(max_length=100)  # Ej: "Vacaciones de Invierno"
    monto_objetivo = models.IntegerField()
    monto_actual = models.IntegerField(default=0)
    fecha_limite = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Meta: {self.nombre} ({self.espacio.nombre})"


class EventoAuditoria(models.Model):
    """Registro inmutable de modificaciones de configuración crítica."""
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE)
    accion = models.CharField(max_length=255)  # Ej: "MODIFICÓ_PRESUPUESTO"
    detalles = models.TextField()  # JSON en formato string con estados previos y nuevos
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Auditoria: {self.accion} - {self.fecha.strftime('%Y-%m-%d %H:%M')}"


class WebhookNonce(models.Model):
    """
    Nonces usados en firmas de ingesta. Evita reutilización (anti-replay)
    dentro de la ventana temporal de 5 minutos.
    """
    perfil = models.ForeignKey(PerfilUsuario, on_delete=models.CASCADE, related_name='nonces')
    nonce = models.CharField(max_length=128)
    timestamp = models.PositiveIntegerField()
    usado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('perfil', 'nonce')
        indexes = [
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"Nonce {self.nonce[:12]}… ({self.perfil.api_key_id})"


class IngestaFallida(models.Model):
    """
    Correos recibidos por el webhook que no pudieron convertirse en Movimiento.
    Permite revisión manual sin reintentos infinitos del cliente GAS.
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='ingestas_fallidas')
    gmail_message_id = models.CharField(max_length=64, unique=True, editable=False)
    conector = models.CharField(max_length=50, blank=True, default='')
    fecha_correo = models.DateTimeField(null=True, blank=True)
    raw_text = models.TextField()
    motivo_error = models.CharField(max_length=255)
    resuelto = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        estado = 'resuelto' if self.resuelto else 'pendiente'
        return f"IngestaFallida {self.gmail_message_id} ({estado})"
