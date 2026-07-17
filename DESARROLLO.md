# Bitácora de Desarrollo - Fintrack CL

Este documento registra cronológicamente las acciones realizadas, archivos creados, lógica implementada y estado del proyecto.

---

## 📅 17 de Julio de 2026

### Inicialización del Proyecto
1. **Configuración de Entorno:**
   - Creado [requirements.txt](file:///c:/Users/SLEP%20IQUIQUE/Desktop/Programacion/FintrackCL/requirements.txt) con dependencias para Django, DRF, python-dotenv, etc.
   - Creado [.env.example](file:///c:/Users/SLEP%20IQUIQUE/Desktop/Programacion/FintrackCL/.env.example) y [.env](file:///c:/Users/SLEP%20IQUIQUE/Desktop/Programacion/FintrackCL/.env) para variables de entorno de configuración.
   - Inicializada esta bitácora ([DESARROLLO.md](file:///c:/Users/SLEP%20IQUIQUE/Desktop/Programacion/FintrackCL/DESARROLLO.md)).
2. **Entorno Virtual e Instalación:**
   - Creado entorno virtual `venv` e instalado dependencias.
3. **Estructura del Proyecto Django:**
   - Creado proyecto Django `fintrack_main` y la aplicación `core`.

### 📅 17 de Julio de 2026 (Continuación)

## Fase 2: Estructura del Backend (Core Django App)
1. **Configuración de `settings.py`:**
   - Carga de variables de entorno mediante `python-dotenv`.
   - Registro de apps: `core`, `rest_framework`, `corsheaders`.
   - Configuración de zona horaria local (`America/Santiago`), idioma (`es-cl`) y modelo de usuario personalizado (`core.Usuario`).
2. **Modelos de Base de Datos (`core/models.py`):**
   - Implementado el modelo de datos relacional de Fintrack CL.
   - Corregidos errores sintácticos del SRS (comas, guiones fantasmas en `TIPO_CHOICES` y el método `.trim()`).
3. **Registro en Django Admin (`core/admin.py`):**
   - Configurada la visualización y búsqueda para todos los modelos.
   - Eventos de auditoría de solo lectura en el panel.
4. **Migraciones:**
   - Generación de migraciones e inicialización exitosa de la base de datos `db.sqlite3` para desarrollo local.

## Fase 3: Ingesta de Datos y Parsers (API & Factory Strategy)
1. **Fábrica de Parsers (`core/parsers/factory.py`):**
   - Implementadas las estrategias `BancoEstadoParserV1` y `SantanderParserV1` usando regex corregidas en Python (`.strip()`).
2. **Autenticación por Firma HMAC (`core/authentication.py`):**
   - Creado `WebhookSignatureAuthentication` para Django REST Framework que valida los encabezados `X-Key-ID`, `X-Signature`, `X-Timestamp`, y `X-Nonce`, implementando protección anti-replay (ventana de 300 segundos).
3. **Controladores y Ruteo (`core/views.py` y `core/urls.py`):**
   - Implementado `IngestaView` (DRF APIView) con manejo de idempotencia absoluta basado en `gmail_message_id`.
   - Implementada la lógica de creación automática de Espacios, Cuentas e Instituciones en base al remitente/conector.
   - Definidos los mapeos de URL a nivel global y de aplicación.

## Fase 4: Frontend Base y Verificación (Templates + Tests)
1. **Templates de Presentación (`core/templates/`):**
   - Creado template `base.html` con carga CDN de Tailwind, Inter font de Google Fonts y Bootstrap Icons.
   - Implementado el Dashboard principal (`core/templates/core/dashboard.html`) en tema oscuro y diseño glassmorphic con actualizaciones automáticas cada 30 segundos mediante HTMX.
   - Diseñado fragmento para lista de transacciones (`core/templates/core/htmx_movimientos_list.html`).
   - Mockup de inicio de sesión (`core/templates/core/login.html`) con comandos útiles para crear superusuarios.
2. **Suite de Pruebas Unitarias (`core/tests.py`):**
   - Implementados 4 tests automatizados de verificación de firmas, ventana temporal anti-replay de 5 minutos, e idempotencia absoluta.
   - Ejecución de pruebas completada exitosamente sin fallos (`Ran 4 tests... OK`).
3. **Directorios de Soporte:**
   - Creado directorio de archivos estáticos `static/` a nivel raíz para evitar advertencias de Django.

## 🛠️ Herramientas de Desarrollo y Soporte
1. **Script de Simulación de Ingesta (`simulate_webhook.py`):**
   - Creado script para emular la transmisión firmada del webhook (GAS) de forma local. Consulta las llaves directamente de los modelos Django de desarrollo y realiza un `POST` al servidor en ejecución.
   - Prueba de integración exitosa: respuesta HTTP 201 confirmada con movimiento `$7.490` en `COPEC S.A.`.

## Fase 5: Página de Perfil y Onboarding
1. **Vista de Perfil (`core/views.py` → `perfil_view`):**
   - Genera las claves API del usuario y el bloque de código de Google Apps Script pre-rellenado.
   - Protegida con `login_required`.
2. **Template de Perfil (`core/templates/core/perfil.html`):**
   - Muestra `api_key_id` (público, copiable) y `api_secret_token` (privado, con toggle de mostrar/ocultar y copiar).
   - Código GAS pre-rellenado con las claves del usuario dentro de un bloque de código con botón de copiar.
   - Instrucciones paso a paso para configurar el trigger en GAS.
3. **Rutas añadidas (`core/urls.py`):** `/perfil/`, `/login/`, `/logout/`.
4. **Navbar actualizado (`base.html`):** Enlace a Dashboard, Mi Perfil, Admin y botón de Cerrar Sesión.

## Fase 6: Login y Sesión Nativa
1. **Vista de Login (`core/views.py` → `login_view`):** Utiliza `AuthenticationForm` de Django con manejo de errores y redirección al parámetro `next`.
2. **Vista de Logout (`core/views.py` → `logout_view`):** Cierra sesión y redirige a `/login/`.
3. **Template de Login (`core/templates/core/login.html`):** Formulario nativo con diseño glassmorphic, validación de errores inline y enlace al Admin de Django.
4. **Dashboard protegido:** `dashboard_view` ahora requiere autenticación con `@login_required(login_url='/login/')`.

## ✅ Estado Actual del Sistema (17 Jul 2026)
- El servidor corre en `http://127.0.0.1:8080`
- Panel de administración operativo en `/admin/` (usuario: `admin`, contraseña: `admin`)
- El webhook de ingesta fue probado exitosamente con `simulate_webhook.py`, insertando un movimiento de `$7.490` en `COPEC S.A.` con la firma HMAC correcta.
- El dashboard muestra el movimiento en tiempo real vía HTMX.
- El puerto 8000 tiene otro proyecto corriendo; usar siempre `8080` para Fintrack CL.

---

## 🔜 Próximos Pasos (Fase 5 en adelante)

### Pendiente de Implementar (Por Prioridad)

1. **[CRÍTICO] Página de Onboarding / Perfil de Usuario:**
   - Mostrar las claves API (`api_key_id` y `api_secret_token`) del usuario en una página segura dentro de la plataforma (no solo en el Admin).
   - El usuario necesita estas claves para configurar su Google Apps Script.

2. **[ALTO] Gestión de Categorías y Reglas de Auto-categorización:**
   - Interfaz para crear y administrar categorías (`Categoria`) dentro de cada Espacio.
   - UI para definir reglas de texto (`ReglaCategoria`) que mapeen automáticamente un comercio a una categoría.

3. **[ALTO] Visualización de Presupuestos y Metas:**
   - Panel de control de presupuestos mensuales (`Presupuesto`) con barras de progreso.
   - Visualización de metas de ahorro (`MetaAhorro`) con indicador de avance.

4. **[MEDIO] Login y Sesión Nativa (sin depender del Admin de Django):**
   - Implementar un formulario de inicio de sesión propio (`/login/`) para que los usuarios regulares no necesiten acceder al Admin de Django.

5. **[MEDIO] Gráficos y Analítica en el Dashboard:**
   - Agregar un gráfico de gastos por categoría (donut chart).
   - Comparativa mensual de ingresos vs. egresos.

6. **[BAJO] Gestión de Múltiples Espacios:**
   - UI para crear, nombrar y alternar entre Espacios de trabajo (ej: "Finanzas Personales", "Gastos del Hogar").
