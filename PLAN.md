# Plan de Implementación — Fintrack CL

**Versión:** 1.0  
**Fecha:** 18 de Julio de 2026  
**Estado del proyecto al inicio del plan:** MVP técnico de ingesta + dashboard básico + login/perfil  
**Documento de requisitos:** [Fintrack CL.md](./Fintrack%20CL.md) (SRS v2.0)  
**Bitácora de avance:** [DESARROLLO.md](./DESARROLLO.md) — cada paso se documenta allí al cerrarlo  

---

## 1. Objetivo

Cerrar el producto en dos entregas:

| Entrega | Alcance | Criterio de “listo” |
|---------|---------|---------------------|
| **MVP local completo** | Fases A–C + E (producto) | App usable en local con `simulate_webhook.py`, UI financiera y onboarding listos |
| **Producción** | Fase D (al final) | Deploy en Oracle VM + Gmail real vía HTTPS |
| **v1.0 SRS** | Todo lo anterior endurecido | Multi-banco, analítica, etc. ya en prod |

---

## 2. Principios de trabajo

1. **Documentar cada paso** en `DESARROLLO.md` (qué se hizo, archivos tocados, cómo probarlo, estado).
2. **Un criterio de salida por fase** antes de avanzar a la siguiente.
3. **No expandir bancos** hasta que BancoEstado + producto mínimo estén sólidos.
4. **Seguridad del webhook** (firma, timestamp, nonce, aislamiento) es no negociable antes de deploy público.

---

## 3. Estado actual (baseline)

### Ya implementado
- Modelos del SRS (`Usuario`, `PerfilUsuario`, `Espacio`, cuentas, movimientos, categorías, reglas, presupuestos, metas, auditoría)
- API de ingesta HMAC (`/api/v1/conectores/ingesta/`)
- Parsers `gmail_bancoestado_v1` y `gmail_santander_v1`
- Idempotencia por `gmail_message_id`
- Dashboard HTMX + login + perfil con código GAS
- Tests: firma válida, firma inválida, anti-replay por timestamp, idempotencia
- Script `simulate_webhook.py`

### Deuda conocida al inicio
- `X-Nonce` no se persiste (replay posible dentro de 5 min)
- Falta test de aislamiento Usuario A vs B
- Parsers frágiles / sin corpus de mails reales
- UI de categorías, reglas, presupuestos, metas y espacios pendiente
- URL del GAS apunta a `127.0.0.1:8080`
- Sin `.gitignore`; `DESARROLLO.md` con “próximos pasos” desactualizados
- Sin deploy Oracle / Postgres / HTTPS

---

## 4. Roadmap por fases

### Fase A — Endurecer el núcleo
**Prioridad:** CRÍTICA  
**Estimación:** 1–2 días  
**Meta:** Ingesta confiable y alineada al SRS de seguridad

| # | Tarea | Estado |
|---|-------|--------|
| A1 | Persistir `X-Nonce` por perfil (anti-replay real) + limpieza de nonces > 5 min | ✅ Completado (2026-07-18) |
| A2 | Tests: aislamiento Usuario A vs B + rechazo de nonce reutilizado | ✅ Completado (2026-07-18) |
| A3 | Modelo/vista `IngestaFallida` para mails no parseados | ✅ Completado (2026-07-18) |
| A4 | Mejorar matching de `ReglaCategoria` (substring real sobre comercio) | ✅ Completado (2026-07-18) |
| A5 | Corpus mínimo BancoEstado (compra / transferencia / ingreso) + tests de parser | ✅ Completado (2026-07-18) |
| A6 | `PUBLIC_BASE_URL` en perfil/GAS (dejar de hardcodear localhost) | ✅ Completado (2026-07-18) |
| A7 | `.gitignore` + alinear bitácora con el plan | ✅ Completado (2026-07-18) |

**Criterio de salida**
- [x] Suite de tests verde incluyendo aislamiento y nonce replay
- [x] Al menos 3 fixtures de mail BancoEstado parsean correctamente
- [x] Perfil genera GAS con URL configurable por entorno
- [x] Paso documentado en `DESARROLLO.md`

**Estado de la fase:** ✅ **Cerrada** — siguiente: Fase B

---

### Fase B — Producto mínimo financiero
**Prioridad:** ALTA  
**Estimación:** 3–5 días  
**Meta:** Organizar dinero sin Admin de Django

| # | Tarea | Estado |
|---|-------|--------|
| B1 | CRUD Categorías por Espacio (HTMX) | ✅ Completado (2026-07-18) |
| B2 | CRUD Reglas de auto-categorización | ✅ Completado (2026-07-18) |
| B3 | Re-categorizar movimiento desde el dashboard | ✅ Completado (2026-07-18) |
| B4 | Filtros dashboard (mes / categoría) + totales con `Sum()` en DB | ✅ Completado (2026-07-18) |
| B5 | Presupuestos mensuales con barra de progreso | ✅ Completado (2026-07-18) |
| B6 | Metas de ahorro con avance | ✅ Completado (2026-07-18) |
| B7 | Crear / listar / cambiar Espacio activo | ✅ Completado (2026-07-18) |
| B8 | Seed de categorías globales Chile (Supermercado, Transporte, etc.) | ✅ Completado (2026-07-18) |

**Criterio de salida**
- [x] Usuario crea categoría + regla “COPEC” → próximos mails salen categorizados
- [x] Puede cambiar categoría de un movimiento a mano
- [x] Ve presupuesto del mes y % consumido
- [x] Puede tener 2 espacios y alternar entre ellos
- [x] Paso documentado en `DESARROLLO.md`

**Estado de la fase:** ✅ **Cerrada** — siguiente: Fase C

---

### Fase C — Onboarding real con Gmail
**Prioridad:** ALTA  
**Estimación:** 1–2 días  
**Meta:** Loop real correo → dashboard

| # | Tarea | Estado |
|---|-------|--------|
| C1 | Wizard/guía onboarding (copiar GAS → trigger cada 10 min) | ✅ Completado (2026-07-18) |
| C2 | Registro de usuario (sin depender del Admin) | ✅ Completado (2026-07-18) |
| C3 | Revelación única / rotación de `api_secret_token` | ✅ Completado (2026-07-18) |
| C4 | Prueba end-to-end con Gmail + BancoEstado real | ✅ Checklist en `ONBOARDING.md` (manual) |
| C5 | Pantalla de “fallidos / pendientes de revisión” | ✅ Completado (2026-07-18) |

**Criterio de salida**
- [x] Un mail real de BancoEstado aparece en el dashboard sin `simulate_webhook` — *requiere túnel/HTTPS; checklist en ONBOARDING.md*
- [x] Usuario nuevo se registra, obtiene claves y configura GAS solo
- [x] Paso documentado en `DESARROLLO.md`

**Estado de la fase:** ✅ **Cerrada a nivel de producto** (C4 Gmail real se hace al final con Fase D, o con túnel opcional) — siguiente en desarrollo local: **Fase E**

---

### Entornos: local vs Gmail real

| Qué | Dónde corre | Cómo probar hoy |
|-----|-------------|-----------------|
| Django + dashboard | Tu PC (`127.0.0.1:8080`) | `runserver` + navegador |
| Firma / parsers / reglas | Tu PC | `manage.py test` + `simulate_webhook.py` |
| Google Apps Script | **Servidores de Google** (no tu PC) | Solo si la URL del backend es pública (túnel o Fase D) |

**Por qué GAS no habla con `127.0.0.1`:** el script no se ejecuta en tu laptop. Google hace el `UrlFetch` desde su nube; para ellos `127.0.0.1` es *su* máquina, no la tuya. En desarrollo local el sustituto correcto es `simulate_webhook.py`.

---

### Fase D — Producción (Oracle Always Free) — **AL FINAL**
**Prioridad:** cuando el producto local esté listo para usuarios reales  
**Estimación:** 2–3 días  
**Meta:** HTTPS público en la VM (Postgres + Nginx + SSL + Gunicorn)

| # | Tarea | Estado |
|---|-------|--------|
| D1 | Postgres + `DATABASE_URL` de producción | ⬜ Pendiente |
| D2 | `DEBUG=False`, `SECRET_KEY` segura, `ALLOWED_HOSTS` | ⬜ Pendiente |
| D3 | Nginx + SSL (Let's Encrypt) | ⬜ Pendiente |
| D4 | Deploy app (Gunicorn/uWSGI) en instancia ARM Oracle | ⬜ Pendiente |
| D5 | Actualizar `PUBLIC_BASE_URL` y smoke test con webhook firmado | ⬜ Pendiente |
| D6 | Checklist de seguridad (sin secretos en repo, admin fuerte) | ⬜ Pendiente |
| D7 | Ejecutar C4 real: Gmail → HTTPS → dashboard (`ONBOARDING.md`) | ⬜ Pendiente |

**Criterio de salida**
- [ ] Endpoint público HTTPS responde 201 a ingesta válida
- [ ] 24–48 h recibiendo movimientos reales sin intervención manual
- [ ] Paso documentado en `DESARROLLO.md`

---

### Fase E — Expansión producto (desarrollo local, **antes del deploy**)
**Prioridad:** MEDIA — continuar aquí mientras no haga falta la VM  
**Estimación:** según demanda  
**Meta:** Cubrir el resto del SRS en local (sigue usando `simulate_webhook.py`)

| # | Tarea | Estado |
|---|-------|--------|
| E1 | Parser BCI + corpus (fixtures / mails de ejemplo) | ✅ Completado (2026-07-18) |
| E2 | Endurecer Santander con más fixtures | ✅ Completado (2026-07-18) |
| E3 | Gráficos (gastos por categoría, mes vs mes) | ✅ Completado (2026-07-18) |
| E4 | Normalización de comercios (`LIDER IQUIQUE` → `Líder`) | ✅ Completado (2026-07-18) |
| E5 | Auditoría visible en UI + export CSV | ✅ Completado (2026-07-18) |
| E6 | Pulido visual de producto (menos prototipo genérico) | ⬜ Opcional / diferido |

**Criterio de salida**
- [x] Features E útiles probadas en local
- [x] SRS v2.0 cubierto en funcionalidad de usuario final (salvo Gmail live y E6 cosmético)
- [ ] Recién entonces → Fase D (deploy)

**Estado de la fase:** ✅ **Cerrada en funcionalidad** (E6 cosmético opcional) — siguiente cuando quieras: **Fase D (deploy)**
---

## 5. Orden de ejecución recomendado

```text
A → B → C  (hecho)
    ↓
E  (seguir desarrollando en local con simulate_webhook)
    ↓
D  (deploy Oracle + HTTPS + Gmail real)  ← al final
```

**Opcional antes de D:** túnel (ngrok / Cloudflare Tunnel) solo si quieres probar GAS ya, sin montar la VM.

Si hay que recortar: producto local sólido (A–C + lo esencial de E) y recién después D.
---

## 6. Convención de documentación (obligatoria)

Al cerrar cada ítem o sub-bloque de una fase, agregar en `DESARROLLO.md`:

```markdown
## 📅 [Fecha] — Fase X: [Nombre del paso]

### Qué se hizo
- ...

### Archivos tocados
- `ruta/archivo.py` — motivo breve

### Cómo probarlo
1. ...

### Estado
- ✅ Completado / ⚠️ Parcial / ❌ Bloqueado (detalle)
```

Actualizar también la columna **Estado** de la tabla de la fase correspondiente en este `PLAN.md` (`⬜` → `✅`).

---

## 7. Cómo arrancamos

1. Crear este plan (`PLAN.md`) y alinear bitácora / `.gitignore`.
2. Ejecutar **Fase A** en orden A1 → A7.
3. Tras criterio de salida de A, continuar con **Fase B**.

---

## 8. Historial de revisiones del plan

| Fecha | Cambio |
|-------|--------|
| 2026-07-18 | v1.0 — Plan inicial acordado; inicio Fase A |
| 2026-07-18 | Fase A: A1/A2/A6/A7 completados (nonce, tests, PUBLIC_BASE_URL, gitignore) |
| 2026-07-18 | Fase A cerrada: A3/A4/A5 (IngestaFallida, reglas substring, corpus BE) |
| 2026-07-18 | Fase B cerrada: organización, filtros, presupuestos, metas, espacios, seed |
| 2026-07-18 | Fase C cerrada: registro, onboarding GAS, secretos, fallidas, ONBOARDING.md |
| 2026-07-18 | Ajuste de orden: E (local) antes de D (deploy); aclaración GAS vs localhost |
| 2026-07-18 | Fase E (E1–E5): BCI/Santander, charts, normalización, CSV, auditoría |
