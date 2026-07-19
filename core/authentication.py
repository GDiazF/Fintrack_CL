import hmac
import hashlib
import time
from django.db import IntegrityError, transaction
from rest_framework import authentication
from rest_framework import exceptions
from core.models import PerfilUsuario, WebhookNonce

# Ventana anti-replay alineada al SRS (5 minutos)
NONCE_TTL_SECONDS = 300


class WebhookSignatureAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # Interceptamos solo el endpoint de ingesta
        if request.path != '/api/v1/conectores/ingesta/':
            return None

        key_id = request.headers.get('X-Key-ID')
        signature = request.headers.get('X-Signature')
        timestamp = request.headers.get('X-Timestamp')
        nonce = request.headers.get('X-Nonce')

        if not all([key_id, signature, timestamp, nonce]):
            raise exceptions.AuthenticationFailed('Faltan cabeceras de seguridad de firma')

        # 1. Ventana de tiempo anti-replay (Max 5 minutos de desfase)
        try:
            ts_int = int(timestamp)
            current_time = int(time.time())
            if abs(current_time - ts_int) > NONCE_TTL_SECONDS:
                raise exceptions.AuthenticationFailed('Petición expirada (Timestamp fuera de rango)')
        except ValueError:
            raise exceptions.AuthenticationFailed('Formato de Timestamp inválido')

        # 2. Recuperar el secreto específico del perfil de usuario
        try:
            perfil = PerfilUsuario.objects.get(api_key_id=key_id)
            api_secret_token = perfil.api_secret_token
        except PerfilUsuario.DoesNotExist:
            raise exceptions.AuthenticationFailed('Credenciales de API no válidas')

        # 3. Validación y verificación criptográfica de la firma
        # Usar el HttpRequest crudo (evita rarezas del wrapper DRF con el body)
        django_request = getattr(request, '_request', request)
        payload_bytes = django_request.body
        message_to_sign = payload_bytes + timestamp.encode('utf-8') + nonce.encode('utf-8')

        digest = hmac.new(
            api_secret_token.encode('utf-8'),
            message_to_sign,
            hashlib.sha256,
        ).digest()

        # Aceptar Base64 (GAS Utilities.base64Encode) o hex (clientes viejos / simulate)
        import base64
        expected_b64 = base64.b64encode(digest).decode('ascii')
        expected_hex = digest.hex()
        sig = (signature or '').strip()
        ok = hmac.compare_digest(expected_b64, sig) or hmac.compare_digest(expected_hex, sig.lower())

        if not ok:
            import logging
            logging.getLogger('fintrack.webhook').warning(
                'HMAC mismatch key_id=%s body_len=%s body_sha256=%s ts=%s nonce=%s sig_recv=%s…',
                key_id,
                len(payload_bytes),
                hashlib.sha256(payload_bytes).hexdigest()[:16],
                timestamp,
                nonce,
                sig[:16],
            )
            raise exceptions.AuthenticationFailed('Firma inválida. Acceso denegado')

        # 4. Registrar nonce (único por perfil) — rechaza reutilización
        self._consume_nonce(perfil, nonce, ts_int)

        return (perfil.user, None)

    def _consume_nonce(self, perfil, nonce, ts_int):
        """Persiste el nonce y limpia entradas fuera de la ventana TTL."""
        cutoff = int(time.time()) - NONCE_TTL_SECONDS
        WebhookNonce.objects.filter(perfil=perfil, timestamp__lt=cutoff).delete()

        try:
            with transaction.atomic():
                WebhookNonce.objects.create(
                    perfil=perfil,
                    nonce=nonce,
                    timestamp=ts_int,
                )
        except IntegrityError:
            raise exceptions.AuthenticationFailed(
                'Nonce reutilizado. Posible ataque de repetición (replay)'
            )
