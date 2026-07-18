# Bitácora de Desarrollo - Fintrack CL

Este documento registra cronológicamente las acciones realizadas, archivos creados, lógica implementada y estado del proyecto.

**Plan maestro:** [PLAN.md](./PLAN.md) — roadmap por fases, criterios de salida y checklist.  
**Especificación:** [Fintrack CL.md](./Fintrack%20CL.md) (SRS v2.0).

**Convención:** al cerrar cada paso de una fase, documentar aquí con el formato de la sección 6 de `PLAN.md` y marcar el ítem correspondiente en el plan.

---

## 📅 17 de Julio de 2026

### Inicialización del Proyecto
1. **Configuración de Entorno:**
   - Creado `requirements.txt` con dependencias para Django, DRF, python-dotenv, etc.
   - Creado `.env.example` y `.env` para variables de entorno de configuración.
   - Inicializada esta bitácora.
2. **Entorno Virtual e Instalación:**
   - Creado entorno virtual `venv` e instalado dependencias.
3. **Estructura del Proyecto Django:**
   - Creado proyecto Django `fintrack_main` y la aplicación `core`.

### Fase 2: Estructura del Backend (Core Django App)
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

### Fase 3: Ingesta de Datos y Parsers (API & Factory Strategy)
1. **Fábrica de Parsers (`core/parsers/factory.py`):**
   - Implementadas las estrategias `BancoEstadoParserV1` y `SantanderParserV1` usando regex corregidas en Python (`.strip()`).
2. **Autenticación por Firma HMAC (`core/authentication.py`):**
   - Creado `WebhookSignatureAuthentication` para Django REST Framework que valida los encabezados `X-Key-ID`, `X-Signature`, `X-Timestamp`, y `X-Nonce`, implementando protección anti-replay (ventana de 300 segundos).
3. **Controladores y Ruteo (`core/views.py` y `core/urls.py`):**
   - Implementado `IngestaView` (DRF APIView) con manejo de idempotencia absoluta basado en `gmail_message_id`.
   - Implementada la lógica de creación automática de Espacios, Cuentas e Instituciones en base al remitente/conector.
   - Definidos los mapeos de URL a nivel global y de aplicación.

### Fase 4: Frontend Base y Verificación (Templates + Tests)
1. **Templates de Presentación (`core/templates/`):**
   - Creado template `base.html` con carga CDN de Tailwind, Inter font de Google Fonts y Bootstrap Icons.
   - Implementado el Dashboard principal (`core/templates/core/dashboard.html`) en tema oscuro y diseño glassmorphic con actualizaciones automáticas cada 30 segundos mediante HTMX.
   - Diseñado fragmento para lista de transacciones (`core/templates/core/htmx_movimientos_list.html`).
   - Mockup de inicio de sesión (`core/templates/core/login.html`) con comandos útiles para crear superusuarios.
2. **Suite de Pruebas Unitarias (`core/tests.py`):**
   - Implementados tests automatizados de verificación de firmas, ventana temporal anti-replay de 5 minutos, e idempotencia absoluta.
3. **Directorios de Soporte:**
   - Creado directorio de archivos estáticos `static/` a nivel raíz.

### Herramientas de Desarrollo y Soporte
1. **Script de Simulación de Ingesta (`simulate_webhook.py`):**
   - Script para emular la transmisión firmada del webhook (GAS) de forma local.
   - Prueba de integración exitosa: respuesta HTTP 201 con movimiento de ejemplo.

### Fase 5: Página de Perfil y Onboarding
1. Vista de perfil con claves API y bloque GAS pre-rellenado.
2. Template de perfil con copy/toggle de secreto.
3. Rutas `/perfil/`, `/login/`, `/logout/`.

### Fase 6: Login y Sesión Nativa
1. Login/logout nativos con `AuthenticationForm`.
2. Dashboard protegido con `@login_required`.

### Estado al cierre del 17 Jul 2026
- Servidor local en `http://127.0.0.1:8080`
- Webhook probado con `simulate_webhook.py`
- Dashboard muestra movimientos vía HTMX

---

## 📅 18 de Julio de 2026 — Plan maestro + inicio Fase A

### Qué se hizo
1. Creado el roadmap completo en [PLAN.md](./PLAN.md) (Fases A–E, criterios de salida, convención de documentación).
2. Alineada esta bitácora con el plan (estado real: onboarding/login ya no son pendientes).
3. Iniciada **Fase A — Endurecer el núcleo**.

### Archivos tocados
- `PLAN.md` — plan de implementación v1.0
- `DESARROLLO.md` — esta actualización
- `.gitignore` — excluye `.env`, `venv/`, `db.sqlite3`, caches, etc.
- `static/.gitkeep` — evita warning de `STATICFILES_DIRS`

### Estado
- ✅ Plan documentado
- ✅ Convención de bitácora definida
- ▶️ Fase A en curso

---

## 📅 18 de Julio de 2026 — Fase A: A1 + A2 + A6 + A7

### Qué se hizo
- **A1:** Modelo `WebhookNonce` + consumo de nonce en `WebhookSignatureAuthentication` (rechazo si se reutiliza; limpieza de nonces fuera de la ventana de 300 s).
- **A2:** Tests nuevos: `test_nonce_reutilizado_rechazado`, `test_aislamiento_usuario_a_vs_b`. Suite: **6 tests OK**.
- **A6:** Setting `PUBLIC_BASE_URL`; el perfil inyecta esa URL en el código GAS (ya no hardcodea localhost a ciegas).
- **A7:** `.gitignore` + bitácora alineada.
- Recreado `venv` en esta máquina (el anterior apuntaba a otra instalación de Python).

### Archivos tocados
- `core/models.py` — modelo `WebhookNonce`
- `core/migrations/0002_webhook_nonce.py` — migración
- `core/authentication.py` — persistencia y validación de nonce
- `core/tests.py` — 6 casos (firma, replay timestamp, nonce, idempotencia, aislamiento)
- `core/admin.py` — registro solo-lectura de nonces
- `core/views.py` — GAS con `settings.PUBLIC_BASE_URL`
- `fintrack_main/settings.py` — `PUBLIC_BASE_URL`
- `.env` / `.env.example` — variable documentada

### Cómo probarlo
```powershell
.\venv\Scripts\python.exe manage.py test core.tests -v 2
.\venv\Scripts\python.exe manage.py runserver 8080
# Con sesión iniciada: abrir /perfil/ y verificar ENDPOINT_URL
```

### Estado
- ✅ A1, A2, A6, A7 completados
- ⬜ A3 `IngestaFallida` — siguiente
- ⬜ A4 matching de reglas
- ⬜ A5 corpus BancoEstado + tests de parser

---

## 📅 18 de Julio de 2026 — Fase A: A3 + A4 + A5 (cierre de fase)

### Qué se hizo
- **A3:** Modelo `IngestaFallida`. Si el parseo falla (sin monto, conector desconocido, excepción), se guarda la falla y se responde **HTTP 200** (`failed_logged`) para que el GAS etiquete el hilo y no reintente infinito. Idempotencia también sobre fallas ya registradas. Admin de solo lectura + flag `resuelto`.
- **A4:** Helper `resolver_categoria_por_reglas` — el patrón debe aparecer **dentro** del comercio (`"COPEC" in "COPEC S.A."`). Prioriza patrones más largos.
- **A5:** Corpus en `core/parsers/corpus_bancoestado.py` (compra, transferencia, ingreso, sin monto). Parser BancoEstado ampliado a esos tres tipos. Tests unitarios de parser + integración con reglas.

### Archivos tocados
- `core/models.py` — `IngestaFallida`
- `core/migrations/0003_ingesta_fallida.py`
- `core/views.py` — registro de fallas + uso del helper de reglas
- `core/categorizacion.py` — matching substring
- `core/parsers/factory.py` — compra / transferencia / ingreso
- `core/parsers/corpus_bancoestado.py` — fixtures de texto
- `core/admin.py` — `IngestaFallidaAdmin`
- `core/tests.py` — 16 tests en total

### Cómo probarlo
```powershell
.\venv\Scripts\python.exe manage.py test core.tests -v 2
# Admin: /admin/core/ingestafallida/ tras forzar un mail sin monto vía simulate_webhook
```

### Estado
- ✅ A3, A4, A5 completados
- ✅ **Fase A cerrada** (criterio de salida cumplido)
- ▶️ Siguiente: **Fase B** (producto mínimo: categorías, reglas UI, presupuestos, espacios)

---

## 📅 18 de Julio de 2026 — Fase B completa (B1–B8)

### Qué se hizo
- **B1–B2:** Página `/organizacion/` con CRUD HTMX de categorías y reglas por espacio.
- **B3:** Selector de categoría en cada fila del dashboard (`POST /movimientos/<id>/categoria/`).
- **B4:** Filtros mes (`YYYY-MM`) y categoría; totales con `Sum()` en DB.
- **B5:** `/presupuestos/` con límite mensual y barra de % consumido.
- **B6:** `/metas/` con avance editable.
- **B7:** Switcher de espacio (sesión) + crear espacio desde Organización.
- **B8:** `python manage.py seed_categorias_chile` → 12 categorías globales.

### Archivos tocados
- `core/utils.py` — espacio activo en sesión
- `core/organizacion_views.py` — vistas de organización / presupuestos / metas
- `core/views.py` — dashboard filtrado + re-categorizar
- `core/urls.py` — rutas nuevas
- `core/templates/core/organizacion.html`, `presupuestos.html`, `metas.html`, `dashboard.html`
- `core/templates/core/partials/*` — listas HTMX, fila movimiento, switcher
- `core/templates/base.html` — nav + CSRF para HTMX
- `core/management/commands/seed_categorias_chile.py`
- `core/tests.py` — 4 tests Fase B (20 total OK)

### Cómo probarlo
```powershell
.\venv\Scripts\python.exe manage.py seed_categorias_chile
.\venv\Scripts\python.exe manage.py runserver 8080
# Login → Organización → crear regla COPEC → Dashboard → cambiar categoría
# Presupuestos / Metas desde el navbar
.\venv\Scripts\python.exe manage.py test core.tests -v 2
```

### Estado
- ✅ **Fase B cerrada**
- ▶️ Siguiente: **Fase C** (onboarding Gmail real, registro, rotación de secretos)

---

## 📅 18 de Julio de 2026 — Fase C (C1–C5)

### Qué se hizo
- **C2:** `/registro/` con `UserCreationForm`; signal crea `PerfilUsuario` + Espacio principal.
- **C3:** Campo `secret_revelado`; revelación única + confirmar / rotar secreto.
- **C1:** Wizard en `/perfil/` + script GAS **completo** (`core/gas_template.py`).
- **C5:** `/fallidas/` para revisar y marcar resueltas; aviso en dashboard.
- **C4:** Checklist manual en [ONBOARDING.md](./ONBOARDING.md) (Gmail real requiere HTTPS/túnel).

### Archivos tocados
- `core/models.py` — `secret_revelado`, `rotar_secret()`, `confirmar_secreto_guardado()`
- `core/migrations/0004_secret_revelado.py`
- `core/signals.py`, `core/apps.py`, `core/auth_views.py`, `core/gas_template.py`
- `core/templates/core/register.html`, `perfil.html`, `fallidas.html`, `login.html`, `dashboard.html`, `base.html`
- `ONBOARDING.md`
- `core/tests.py` — 23 tests OK

### Cómo probarlo
```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver 8080
# Abrir /registro/ → /perfil/ → copiar GAS → confirmar secreto
# Fallidas: forzar mail sin monto con simulate_webhook (raw_text sin $)
.\venv\Scripts\python.exe manage.py test core.tests -v 1
```

### Estado
- ✅ **Fase C cerrada** (C4 Gmail real = al deploy o con túnel; en local usar `simulate_webhook.py`)
- ▶️ Siguiente en local: **Fase E** — deploy (**Fase D**) queda para el final

---

## 📅 18 de Julio de 2026 — UI: menú cascade + responsive

### Qué se hizo
- Navbar: menú usuario (cascade) con Mi perfil, Onboarding, Admin (si staff), Salir
- `/perfil/` edita nombre/apellido/email/teléfono; `/onboarding/` tiene GAS y secretos
- Dashboard: sin scroll horizontal en desktop; tarjetas en móvil; tipo visible
- Layout más limpio en organización, presupuestos, metas, fallidas, auditoría

### Cómo verlo
Recargar http://127.0.0.1:8080 (hard refresh si hace falta)

### Estado
- ✅ UI actualizada · tests 27 OK

---

## 📅 18 de Julio de 2026 — Fase E (E1–E5)

### Qué se hizo
- **E1–E2:** Parser `gmail_bci_v1` + Santander ampliado; corpus en `corpus_bci.py` / `corpus_santander.py`.
- **E3:** Donut gastos por categoría + barras ingresos/egresos mensuales (Chart.js en dashboard).
- **E4:** `AliasComercio` + `resolver_comercio()` (`LIDER IQUIQUE` → `Líder`).
- **E5:** `/export/csv/` y `/auditoria/` (log al re-categorizar).
- **E6:** Diferido (pulido visual cosmético).

### Archivos tocados
- `core/parsers/factory.py`, `corpus_bci.py`, `corpus_santander.py`
- `core/normalizacion.py`, `core/models.py` (`AliasComercio`), migración `0005`
- `core/reportes_views.py`, `core/views.py`, `core/urls.py`
- `core/templates/core/dashboard.html`, `auditoria.html`, `base.html`
- `core/tests.py` — **27 tests OK**

### Cómo probarlo
```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver 8080
# Dashboard: gráficos + botón CSV
# Cambiar categoría de un movimiento → ver /auditoria/
.\venv\Scripts\python.exe manage.py test core.tests -v 1
```

### Estado
- ✅ **Fase E funcional cerrada**
- ⬜ E6 opcional
- ▶️ Cuando quieras producción: **Fase D** (Oracle / Postgres / Nginx / SSL)

---

## ✅ Estado Actual del Sistema (18 Jul 2026)

| Área | Estado |
|------|--------|
| Fases A–C | ✅ |
| Fase E (producto local) | ✅ E1–E5 |
| Suite tests | ✅ 27 OK |
| Gmail live | ⬜ Tras Fase D o túnel |
| Fase D — deploy Oracle | ⬜ Al final |

- Puerto local: **8080**
- Flujo local: `runserver` + `simulate_webhook.py`

---

## 🔜 Próximos pasos

1. Probar en local dashboard / CSV / auditoría / simulate_webhook
2. **Fase D** cuando quieras desplegar en la VM Oracle
3. (Opcional) E6 pulido visual

---

## 📅 18 de Julio de 2026 — Email: verificación + recuperación

### Hecho
1. SMTP vía `.env` (Gmail App Password); sin `EMAIL_HOST` → backend consola.
2. Registro exige email y deja la cuenta pendiente hasta `/verificar/<uid>/<token>/`.
3. Reenvío de verificación y bloqueo de login si no está verificado.
4. Recuperación de contraseña: `/password-reset/` (flujo Django + templates Fintrack).
5. Campo `PerfilUsuario.email_verificado` (default True para no romper usuarios existentes).
6. Admin muestra y filtra `email_verificado`.

### Config local / Gmail
Ver `.env.example`. Con Gmail:
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu@gmail.com
EMAIL_HOST_PASSWORD=xxxx-app-password
DEFAULT_FROM_EMAIL=Fintrack CL <tu@gmail.com>
```

### Probar
```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py test core.tests.EmailAuthTests -v 1
```

### Estado
- ✅ Verificación + reset listos en local (mails en consola sin SMTP)
- ▶️ Siguiente grande: **Fase D** (deploy)
