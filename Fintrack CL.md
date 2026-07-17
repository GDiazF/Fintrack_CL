# **📑 ESPECIFICACIÓN DE REQUISITOS DE SOFTWARE (SRS)** 

# **Proyecto: Fintrack CL — Plataforma de Gestión Financiera Automatizada** 

**Versión:** 2.0 (Grado de Producción para MVP) 

**Estado:** Aprobado para Desarrollo 

# **1. Visión General del Producto** 

Fintrack CL es una plataforma SaaS de finanzas personales multiusuario y estructurada por **Espacios Lógicos de Trabajo** , diseñada específicamente para el contexto financiero chileno. Resuelve la fricción histórica de la ingesta de datos (la necesidad de ingresar gastos manualmente o entregar contraseñas bancarias) mediante la captura automatizada y en tiempo real de las notificaciones de transacciones enviadas por correo electrónico (caso de uso crítico: **BancoEstado** ). 

El sistema utiliza un cliente nativo ultra-ligero en **Google Apps Script (GAS)** que actúa únicamente como un "mensajero" seguro, delegando toda la lógica de parsing, normalización y asignación al backend centralizado en **Django** . 

# **1.1 Pilares Estratégicos** 

- **Fricción Cero (UX):** El usuario final nunca entrega sus credenciales de acceso bancario. La integración se realiza mediante la API nativa de su propia cuenta de Google de forma privada. 

- **Eficiencia de Infraestructura:** Diseñado bajo restricciones de consumo para operar al 100% dentro de la capa _Always Free_ de Oracle Cloud (Instancias ARM con Ampere). 

- **Seguridad Aislada por Usuario:** Autenticación estricta por firma criptográfica basada en llaves únicas por perfil para evitar la inyección de transacciones falsas y mitigar ataques de denegación de servicio o repetición ( _anti-replay_ ). 

- **Desacoplamiento Total:** El cliente de captura (GAS) no posee lógica de negocio; si el formato del correo del banco cambia, el sistema se repara centralizadamente en el backend sin intervención del usuario. 

# **2. Arquitectura del Sistema y Flujo de Datos** 

[ Gmail de Usuario (BancoEstado) ] 

- (Filtro optimizado: correos sin etiqueta "fintrack-procesado") 

[ Google Apps Script (Trigger Cron cada 10 min) ] 

│ 

▼ (HTTPS POST + Payload Crudo + X-Signature HMAC-SHA256) 

[ Proxy Nginx (SSL / Capa de Red) ] 

│ 

▼ 

[ Django REST Framework (Middleware de Validación de Firma por Perfil) ] 

│ 

── ├ ▶ [ ParserFactory (Ruteo Dinámico al Conector v1/v2) ] 

└──▶ [ Base de Datos PostgreSQL / SQLite (Garantía de Idempotencia) ] 

│ 

▼ 

[ Frontend: Django Templates + HTMX + Tailwind CSS (Renderizado Dinámico) ] 

# **3. Modelo de Datos Completo (models.py)** 

Python 

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

api_key_id = models.CharField(max_length=32, unique=True, editable=False) # Identificador público de la llave 

api_secret_token = models.CharField(max_length=64, unique=True, editable=False) # Secreto criptográfico privado 

creado_en = models.DateTimeField(auto_now_add=True) 

def save(self, *args, **kwargs): 

if not self.api_key_id: 

self.api_key_id = f"ft_key_{secrets.token_hex(12)}" 

if not self.api_secret_token: 

self.api_secret_token = f"ft_secret_{secrets.token_urlsafe(32)}" 

super().save(*args, **kwargs) 

class Espacio(models.Model): 

"""Aislamiento lógico (Multi-tenant elástico). Permite finanzas individuales o compartidas.""" 

nombre = models.CharField(max_length=100)  # Ej: "Finanzas Personales", "Gastos Hogar" 

administrador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='espacios_administrados') 

miembros = models.ManyToManyField(Usuario, 

related_name='espacios_compartidos') 

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

institucion = models.ForeignKey(InstitucionFinanciera, 

on_delete=models.PROTECT, related_name='cuentas') 

nombre = models.CharField(max_length=100)  # Ej: "CuentaRUT", "Tarjeta Visa", "Efectivo Bolsillo" 

identificador_conector = models.CharField(max_length=50, blank=True, null=True) # Ej: "1234" (4 dígitos tarjeta) 

es_predeterminada = models.BooleanField(default=False) 

creado_en = models.DateTimeField(auto_now_add=True) 

class Meta: 

unique_together = ('espacio', 'institucion', 'nombre') 

class Comercio(models.Model): 

"""Normaliza las cadenas de texto del retail (Ej: 'LIDER IQUIQUE' apunta a 'Líder').""" 

nombre_fantasia = models.CharField(max_length=150, unique=True)  # Ej: "Líder" 

categoria_sugerida = models.ForeignKey('Categoria', on_delete=models.SET_NULL, null=True, blank=True) 

class Categoria(models.Model): 

"""Categorías de organización del dinero. Si espacio es null, es una categoría global del sistema.""" 

espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, null=True, blank=True, related_name='categorias') 

nombre = models.CharField(max_length=100) 

color_hex = models.CharField(max_length=7, default="#3498DB") 

icono = models.CharField(max_length=50, default="bi-wallet") 

class Meta: 

unique_together = ('espacio', 'nombre') 

class ReglaCategoria(models.Model): 

"""Mapeo automático basado en patrones de texto personalizados por Espacio.""" 

espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='reglas') 

patron_texto = models.CharField(max_length=100)  # Ej: "COPEC", "STARBUCKS" 

categoria_destino = models.ForeignKey(Categoria, on_delete=models.CASCADE) 

class Moneda(models.Model): 

"""Soporte multi-moneda completo (Evita lógica dura en los modelos).""" 

codigo_iso = models.CharField(max_length=3, unique=True)  # Ej: "CLP", "USD", "EUR", "UF" 

simbolo = models.CharField(max_length=10)  # Ej: "$", "US$", "UF" 

decimales = models.PositiveIntegerField(default=0) 

class Movimiento(models.Model): 

"""El núcleo financiero del sistema. Todo flujo de dinero es un Movimiento.""" 

TIPO_CHOICES = [ 

('EGRESO', 'Gasto / Compra / Retiro'), 

- ('INGRESO', 'Sueldo / Abono / Depósito'), 

- ('TRANSFERENCIA', 'Transferencia entre Cuentas'), 

('COMISION', 'Comisión / Interés Cobrado'), 

] 

cuenta = models.ForeignKey(CuentaFinanciera, on_delete=models.CASCADE, related_name='movimientos') 

comercio = models.ForeignKey(Comercio, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos') 

comercio_raw = models.CharField(max_length=255)  # Texto original extraído del 

correo 

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

class Presupuesto(models.Model): 

"""Límites de gastos mensuales por categoría.""" 

espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='presupuestos') 

categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='presupuestos') 

monto_limite = models.IntegerField() 

mes = models.PositiveIntegerField() 

anio = models.PositiveIntegerField() 

class Meta: 

unique_together = ('espacio', 'categoria', 'mes', 'anio') 

class MetaAhorro(models.Model): 

"""Objetivos financieros motivacionales.""" 

espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE, related_name='metas') 

nombre = models.CharField(max_length=100)  # Ej: "Vacaciones de Invierno" 

monto_objetivo = models.IntegerField() 

monto_actual = models.IntegerField(default=0) 

fecha_limite = models.DateField(blank=True, null=True) 

class EventoAuditoria(models.Model): 

"""Registro inmutable de modificaciones de configuración crítica.""" 

usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True) 

espacio = models.ForeignKey(Espacio, on_delete=models.CASCADE) 

accion = models.CharField(max_length=255)  # Ej: "MODIFICÓ_PRESUPUESTO" 

detalles = models.TextField()  # JSON en formato string con estados previos y nuevos 

fecha = models.DateTimeField(auto_now_add=True) 

# **4. Reglas de Negocio Estrictas (Lógica de Servidor)** 

# **4.1 Arquitectura del Conector Desacoplado (Strategy Pattern)** 

El cliente de Google Apps Script **no realiza ninguna labor de parsing ni validación por expresiones regulares** . Su único propósito es recolectar y transmitir. El flujo opera de la siguiente manera: 

1. El script envía el cuerpo de texto plano e inalterado (raw_text), el identificador global gmail_message_id y su clave pública api_key_id. 

2. El backend procesa el payload, valida la firma criptográfica usando la clave privada correspondiente de ese usuario, y delega el cuerpo a la clase ParserFactory. 

3. ParserFactory.get(conector) resuelve dinámicamente la estrategia de extracción según el conector versionado indicado (ej: gmail_bancoestado_v1). 

# **4.2 Control de Duplicados (Idempotencia)** 

El campo gmail_message_id actúa como clave primaria lógica de control de ingesta. Si el backend recibe una petición HTTP con un ID que ya existe en la tabla de Movimiento, la petición se captura en una estructura try-except de base de datos a nivel de restricción de unicidad (IntegrityError), aborta el guardado y retorna de inmediato una respuesta exitosa HTTP 200 OK al cliente de Google para cerrar el ciclo de reintentos de forma limpia. 

# **5. Especificaciones de la API de Ingesta** 

- **Endpoint:** /api/v1/conectores/ingesta/ 

- **Método:** POST 

- **Encabezados Requeridos:** 

   - X-Key-ID: Identificador de la API Key pública del usuario (api_key_id). 

   - X-Signature: Firma SHA256 calculada en el cliente GAS. 

   - X-Timestamp: Tiempo Unix en segundos del momento de emisión del cliente. 

   - X-Nonce: Cadena aleatoria única por petición. 

- **Cuerpo del Payload (JSON):** 

JSON 

{ 

"conector": "gmail_bancoestado_v1", 

"gmail_message_id": "msg_ch17072026_xyz999", 

"fecha_correo": "2026-07-17T18:32:00Z", 

"raw_text": "BancoEstado: Hola Diego, confirmamos tu compra por un monto de 

$4.990 en CAFETERIA IQUIQUE con tu tarjeta *5678 el 17/07/2026." 

} 

# **6. Código del Servidor: Middleware de Firma de Usuario (middleware.py)** 

Garantiza la autenticidad, integridad y aislamiento completo por usuario antes de tocar la base de datos. 

Python 

import hmac 

import hashlib 

import time 

from django.http import JsonResponse 

from django.utils.deprecation import MiddlewareMixin 

from core.models import PerfilUsuario 

class WebhookSignatureMiddleware(MiddlewareMixin): 

def process_view(self, request, view_func, view_args, view_kwargs): 

if request.path != '/api/v1/conectores/ingesta/': 

return None 

key_id = request.headers.get('X-Key-ID') 

signature = request.headers.get('X-Signature') 

timestamp = request.headers.get('X-Timestamp') 

nonce = request.headers.get('X-Nonce') 

if not all([key_id, signature, timestamp, nonce]): 

return JsonResponse({'error': 'Faltan cabeceras de seguridad de firma'}, status=401) 

# 1. Ventana de tiempo anti-replay (Max 5 minutos de desfase) 

try: 

if abs(int(time.time()) - int(timestamp)) > 300: 

return JsonResponse({'error': 'Petición expirada (Timestamp fuera de rango)'}, status=401) 

except ValueError: 

return JsonResponse({'error': 'Formato de Timestamp inválido'}, status=400) 

# 2. Recuperar el secreto específico de ESTE usuario (Aislamiento total) 

try: 

perfil = PerfilUsuario.objects.get(api_key_id=key_id) 

api_secret_token = perfil.api_secret_token 

# Inyectamos el usuario en el request para uso posterior en la vista 

request.api_user = perfil.user 

except PerfilUsuario.DoesNotExist: 

return JsonResponse({'error': 'Credenciales de API no válidas'}, status=401) 

# 3. Validación y verificación criptográfica de la firma 

payload_bytes = request.body 

message_to_sign = payload_bytes + timestamp.encode('utf-8') + nonce.encode('utf-8') 

expected_signature = hmac.new( 

api_secret_token.encode('utf-8'), 

message_to_sign, 

hashlib.sha256 

).hexdigest() 

if not hmac.compare_digest(expected_signature, signature): 

return JsonResponse({'error': 'Firma inválida. Acceso denegado'}, status=401) 

return None 

# **7. Cliente de Captura: Google Apps Script Multi-Banco (Desacoplado)** 

JavaScript 

function enviarCorreosAlServidor() { 

// Credenciales específicas obtenidas desde el onboarding de la plataforma 

var API_KEY_ID = "ft_key_REEMPLAZAR_DESDE_ONBOARDING"; 

var API_SECRET = "ft_secret_REEMPLAZAR_DESDE_ONBOARDING"; 

var ENDPOINT_URL = "https://tu-app-oracle.com/api/v1/conectores/ingesta/"; 

var ETIQUETA_PROCESADO = "fintrack-procesado"; 

var etiqueta = GmailApp.getUserLabelByName(ETIQUETA_PROCESADO) || GmailApp.createLabel(ETIQUETA_PROCESADO); 

// Búsqueda multi-banco parametrizada en un solo barrido eficiente 

var query = "(from:bancoestado.cl OR from:santander.cl OR from:bci.cl) -label:" + ETIQUETA_PROCESADO; 

var hilos = GmailApp.search(query, 0, 15); 

for (var i = 0; i < hilos.length; i++) { 

var mensajes = hilos[i].getMessages(); 

for (var j = 0; j < mensajes.length; j++) { 

var mensaje = mensajes[j]; 

var etiquetasActuales = hilos[i].getLabels(); 

var revisado = etiquetasActuales.some(function(l) { return l.getName() === ETIQUETA_PROCESADO; }); 

if (!revisado) { 

// Resolver de qué conector viene según el emisor del correo 

var remitente = mensaje.getFrom(); 

var conectorId = "gmail_bancoestado_v1"; // por defecto 

if (remitente.includes("santander.cl")) conectorId = "gmail_santander_v1"; 

if (remitente.includes("bci.cl")) conectorId = "gmail_bci_v1"; 

var payloadObj = { 

"conector": conectorId, 

"gmail_message_id": mensaje.getId(), 

"fecha_correo": mensaje.getDate().toISOString(), 

"raw_text": mensaje.getPlainBody() 

}; 

var payloadStr = JSON.stringify(payloadObj); 

var timestamp = Math.floor(Date.now() / 1000).toString(); 

var nonce = Math.random().toString(36).substring(2, 12); 

var stringParaFirmar = payloadStr + timestamp + nonce; 

var firmaBytes = Utilities.computeHmacSignature(Utilities.MacAlgorithm.HMAC_SHA_256, stringParaFirmar, API_SECRET); 

var firmaHex = firmaBytes.map(function(byte) { 

return ('0' + (byte & 0xFF).toString(16)).slice(-2); 

}).join(''); 

var opciones = { 

"method" : "post", 

"contentType": "application/json", "headers": { 

"X-Key-ID": API_KEY_ID, 

"X-Signature": firmaHex, 

"X-Timestamp": timestamp, 

"X-Nonce": nonce 

}, 

"payload" : payloadStr, 

"muteHttpExceptions": true 

}; 

try { 

var respuesta = UrlFetchApp.fetch(ENDPOINT_URL, opciones); 

var codigoEstado = respuesta.getResponseCode(); 

if (codigoEstado === 200 || codigoEstado === 201) { 

hilos[i].addLabel(etiqueta); 

} 

} catch(error) { 

Logger.log("Fallo de red en transmisión de webhook: " + error.toString()); 

} 

} 

} 

} 

} 

# **8. Arquitectura de Código del Backend: parsers/factory.py** 

Implementación limpia del patrón _Factory Strategy_ para escalar a nuevos bancos agregando módulos aislados que implementen la misma interfaz sin afectar el núcleo del sistema. 

Python 

# core/parsers/factory.py 

import re 

from django.utils.dateparse import parse_datetime 

class BaseParser: 

def parsear(self, raw_text): 

raise NotImplementedError("Cada parser debe implementar su propio método de extracción") 

class BancoEstadoParserV1(BaseParser): 

def parsear(self, raw_text): 

# Expresiones regulares específicas de BancoEstado v1 

monto_match = re.search(r"monto de \$([0-9\.]+)", raw_text, re.IGNORECASE) 

comercio_match = re.search(r"en ([A-Z0-9\s\-\.]+)", raw_text) 

tarjeta_match = re.search(r"tarjeta\s*\*([0-9]{4})", raw_text, re.IGNORECASE) 

return { 

'monto': int(monto_match.group(1).replace('.', '')) if monto_match else None, 

'comercio_raw': comercio_match.group(1).trim() if comercio_match else "COMERCIO DESCONOCIDO", 

'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None, 

'tipo': 'EGRESO' 

} 

class SantanderParserV1(BaseParser): 

def parsear(self, raw_text): 

# Lógica de extracción adaptada al formato de correos Santander v1 

monto_match = re.search(r"Notifica Compra por \$([0-9\.]+)", raw_text) 

comercio_match = re.search(r"Lugar:\s*([A-Z0-9\s\-\.]+)", raw_text, re.IGNORECASE) 

return { 

'monto': int(monto_match.group(1).replace('.', '')) if monto_match else None, 

'comercio_raw': comercio_match.group(1).strip() if comercio_match else "SANTANDER_ESTABLECIMIENTO", 

'identificador_tarjeta': None, 

'tipo': 'EGRESO' 

} 

class ParserFactory: 

_STRATEGIES = { 

'gmail_bancoestado_v1': BancoEstadoParserV1(), 

'gmail_santander_v1': SantanderParserV1(), 

} 

@classmethod 

def get(cls, conector_id): 

return cls._STRATEGIES.get(conector_id, None) 

# **9. Entorno, Estructura y Flujo de Despliegue** 

# **9.1 Estructura de Directorios del Proyecto** 

fintrack_project/ 

│ 

├── .env                  # Variables críticas de entorno (Excluido de Git) 

├── manage.py 

│ 

├── fintrack_main/        # Configuración del Servidor Global 

│   ├── __init__.py 

│   ├── settings.py       # Declarar AUTH_USER_MODEL = 'core.Usuario' 

│   ├── urls.py 

│   └── wsgi.py │ 

└── core/                 # Aplicación Base del Core de Negocio 

├── __init__.py 

├── admin.py 

├── middleware.py     # Componente de filtrado y firmas por Perfil 

├── models.py         # Arquitectura relacional expuesta arriba 

├── urls.py 

├── views.py 

│ 

├── parsers/          # Fábrica y estrategias modulares de parsing 

│   ├── __init__.py │   ├── factory.py │   └── ... │ 

└── templates/        # Capa de presentación reactiva con HTMX 

├── base.html └── core/ ├── dashboard.html └── htmx_movimientos_list.html 

# **9.2 Variables de Entorno Obligatorias (.env)** 

Fragmento de código 

DEBUG=False 

SECRET_KEY=django_core_secret_generada_aleatoriamente_aqui 

ALLOWED_HOSTS=tuapp.oraclecloud.com,localhost 

DATABASE_URL=postgres://usuario:password@localhost:5432/fintrack_db 

# **9.3 Estrategia de Pruebas Unitarias Críticas (Garantías)** 

El plan de testing automatizado debe cubrir obligatoriamente tres vectores antes de ir a producción: 

1. **Test de Aislamiento de Llaves:** Verificar que una firma válida con una clave 

filtrada de un "Usuario A" no permita escribir en los Espacios del "Usuario B". 

2. **Test de Ventana Temporal (Anti-Replay):** Validar que el middleware devuelva un HTTP 401 Unauthorized si se recibe una firma correcta cuyo X-Timestamp tenga más de 300 segundos de antigüedad. 

3. **Test de Idempotencia Práctica:** Inyectar el mismo payload con el mismo gmail_message_id dos veces consecutivas. El sistema debe arrojar un HTTP 201 Created en la primera iteración y un HTTP 200 OK en la segunda sin duplicar registros ni alterar balances. 

