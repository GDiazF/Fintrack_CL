"""Eco de diagnóstico HMAC (piloto). Compara firma recibida vs esperada."""

import base64
import hashlib
import hmac
import json

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import PerfilUsuario


class HmacEchoView(APIView):
    """
    POST /api/v1/conectores/hmac-echo/
    Sin auth. Devuelve qué body llegó y si la firma calzaría.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        key_id = request.headers.get('X-Key-ID', '')
        signature = (request.headers.get('X-Signature') or '').strip()
        timestamp = request.headers.get('X-Timestamp', '')
        nonce = request.headers.get('X-Nonce', '')
        body = request.body

        perfil = PerfilUsuario.objects.filter(api_key_id=key_id).first()
        if not perfil:
            return Response({
                'ok': False,
                'error': 'key_id no existe',
                'key_id': key_id,
                'body_len': len(body),
                'body_preview': body[:120].decode('utf-8', errors='replace'),
            }, status=400)

        msg = body + timestamp.encode('utf-8') + nonce.encode('utf-8')
        digest = hmac.new(
            perfil.api_secret_token.encode('utf-8'),
            msg,
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(digest).decode('ascii')
        expected_b64url = base64.urlsafe_b64encode(digest).decode('ascii')
        expected_hex = digest.hex()

        return Response({
            'ok': signature in (expected_b64, expected_b64url, expected_hex),
            'body_len': len(body),
            'body_sha256': hashlib.sha256(body).hexdigest(),
            'body_preview': body[:160].decode('utf-8', errors='replace'),
            'timestamp': timestamp,
            'nonce': nonce,
            'sig_received': signature,
            'expected_b64': expected_b64,
            'expected_b64url': expected_b64url,
            'expected_hex': expected_hex,
            'secret_prefix': perfil.api_secret_token[:16],
        })
