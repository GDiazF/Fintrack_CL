# Onboarding Gmail + BancoEstado (C4)

## Desarrollo local (ahora)

No necesitas Gmail ni HTTPS para seguir avanzando.

| Herramienta | Uso |
|-------------|-----|
| `python manage.py runserver 8080` | App en el navegador |
| `python simulate_webhook.py` | Simula lo que haría el GAS (firma HMAC + POST) |
| `/perfil/` | Wizard y script listos para cuando haya URL pública |

**Por qué el GAS no pegará a `127.0.0.1`:** Apps Script corre en los servidores de Google. Su `UrlFetch` a `http://127.0.0.1:8080` apunta al localhost de *Google*, no al tuyo. Eso es normal en local.

## Cuándo sí probar Gmail de verdad

1. **Opción preferida (final):** Fase D — deploy en Oracle con HTTPS, luego este checklist.  
2. **Opción temporal:** túnel (ngrok / Cloudflare Tunnel) → poner esa URL en `PUBLIC_BASE_URL` → pegar el script de `/perfil/`.

## Checklist Gmail real (cuando tengas URL pública)

### Requisitos
- [ ] `PUBLIC_BASE_URL` = URL HTTPS alcanzable desde Internet
- [ ] Cuenta en `/registro/` y secreto confirmado en `/perfil/`
- [ ] `python manage.py seed_categorias_chile`
- [ ] (Opcional) Regla `COPEC` → Combustible

### Pasos GAS
1. [script.google.com](https://script.google.com) → proyecto nuevo  
2. Pegar el script completo desde `/perfil/`  
3. Ejecutar `enviarCorreosAlServidor` una vez → autorizar  
4. Trigger cada 10 minutos  
5. Generar / recibir un mail BancoEstado  

### Verificación
- [ ] Etiqueta `fintrack-procesado` en Gmail  
- [ ] Movimiento en el Dashboard  
- [ ] Fallos de parseo en `/fallidas/`  
- [ ] Sin duplicados al reintentar  

### Notas
- Tras rotar el secreto, vuelve a pegar el script en GAS.
