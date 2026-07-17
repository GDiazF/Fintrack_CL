import hmac
import hashlib
import time
from rest_framework import authentication
from rest_framework import exceptions
from core.models import PerfilUsuario

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
            if abs(current_time - ts_int) > 300:
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
        payload_bytes = request.body
        message_to_sign = payload_bytes + timestamp.encode('utf-8') + nonce.encode('utf-8')
        
        expected_signature = hmac.new(
            api_secret_token.encode('utf-8'),
            message_to_sign,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise exceptions.AuthenticationFailed('Firma inválida. Acceso denegado')

        # Autenticación exitosa, retornamos al usuario asociado y None para auth info
        return (perfil.user, None)
